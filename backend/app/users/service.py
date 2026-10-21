from collections.abc import Callable
import logging
from uuid import UUID

from asyncpg import UniqueViolationError

from app.auth.utils import hash_password_async
from app.errors import RequestValueError
from app.service import UnitOfWork
from app.tracing import traced, trace_span
from app.decks.archiver import DeckArchiveWorkflow
from app.users.errors import (
    PermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
    translate_user_integrity_error,
)
from app.users.models import User, UserSettings
from app.users.schemas import CreateUserRequest, InternalUser, InternalUserSettings, InternalUserWithSettings, UpdateUserSettingsRequest, UpdateUserRequest, UserProfileResponse, UserSettingsUpdateData, UserUpdateData
from sqlalchemy.exc import IntegrityError

from app.redis.service import RedisCacheService
from app.redis.invalidation import CacheInvalidator, scopes
from app.redis.outbox import cache_invalidation_message
from app.common.types import Username

logger = logging.getLogger(__name__)

class UserService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
        cache_invalidator: CacheInvalidator,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service
        self.cache_invalidator = cache_invalidator

    # helpers
    async def _get_by_uuid(
        self, 
        uow: UnitOfWork, 
        user_uuid: UUID,
        for_update: bool = False,
        get_settings: bool = False,
    ) -> User:
        user = await uow.user_repo.get_by_uuid(
            user_uuid=user_uuid,
            for_update=for_update,
            include_settings=get_settings,
        )
        if user is None:
            raise UserNotFoundError(f"User with uuid={user_uuid} not found")
        return user

    # read

    @traced("users.service.get_user_profile")
    async def get_user_profile(
        self,
        viewer_id: int | None,
        username: Username,
    ) -> UserProfileResponse:   
        async with self.uow_factory() as uow:
            profile = await uow.user_repo.get_user_profile(
                profile_username=username,
            )

            if profile is None:
                raise UserNotFoundError()
            
            user, total_decks, public_decks, total_saves_count = profile

            is_own_profile = (
                viewer_id is not None
                and viewer_id == user.id
            )

            deck_count = (
                total_decks
                if is_own_profile
                else public_decks
            )

            return UserProfileResponse(
                uuid=user.uuid,
                username=user.username,
                created_at=user.created_at,
                deck_count=deck_count,
                total_saves_count=total_saves_count,              
            )

    @traced("users.service.get_by_uuid")
    async def get_by_uuid(
        self,
        user_uuid: UUID,
    ) -> InternalUser:
        user_lookup = await self.cache_service.get_cached_users_by_uuids(
            user_uuids=[user_uuid],
        )

        cached_user = user_lookup.cached.get(user_uuid)
        if cached_user is not None:
            return cached_user

        async with self.uow_factory() as uow:
            user = await self._get_by_uuid(
                uow=uow,
                user_uuid=user_uuid,
                get_settings=False,
            )

            internal_user = InternalUser.model_validate(obj=user)

            await self.cache_service.cache_users(
                users=[internal_user],
            )

            return internal_user

    @traced("users.service.get_by_uuid_with_settings")
    async def get_by_uuid_with_settings(
        self,
        user_uuid: UUID,
    ) -> InternalUserWithSettings:
        user_lookup = await self.cache_service.get_cached_users_by_uuids(
            user_uuids=[user_uuid],
        )
        cached_user = user_lookup.cached.get(user_uuid)
        if cached_user is not None:
            user_settings_lookup = (
                await self.cache_service.get_cached_users_settings(
                    user_ids=[cached_user.id],
                )
            )

            cached_user_settings = (
                user_settings_lookup.cached.get(cached_user.id)
            )
            if cached_user_settings is not None:
                return InternalUserWithSettings.from_parts(
                    user=cached_user,
                    settings=cached_user_settings,
                )

        async with self.uow_factory() as uow:
            user = await self._get_by_uuid(
                uow=uow,
                user_uuid=user_uuid,
                for_update=False,
                get_settings=True,
            )
            internal_user = InternalUser.model_validate(obj=user)
            internal_user_settings = InternalUserSettings.model_validate(
                obj=user.settings,
            )

            await self.cache_service.cache_users(
                users=[internal_user],
            )
            await self.cache_service.cache_users_settings(
                users_settings=[internal_user_settings],
            )

            return InternalUserWithSettings.from_parts(
                user=internal_user,
                settings=internal_user_settings,
            )

    # checked
    @traced("users.service.create_user")
    async def create_user(
            self,
            payload: CreateUserRequest,
    ) -> InternalUserWithSettings:
        try:
            async with self.uow_factory() as uow:
                user_data = payload.model_dump(exclude={"password"})
                user = User(
                    **user_data,
                    hashed_password=await hash_password_async(payload.password),
                )
                uow.user_repo.add(user)
                await uow.flush()
                user_settings = UserSettings(
                    user_id=user.id,
                    locale="ru-RU",
                    theme="light",
                    show_previews_for_long=True,
                )
                uow.user_settings_repo.add(user_settings)
                await uow.flush()
                result = InternalUserWithSettings.from_parts(
                    user=InternalUser.model_validate(obj=user),
                    settings=InternalUserSettings.model_validate(obj=user_settings),
                )
                await uow.commit()
                return result
        except IntegrityError as e:
            domain_error = translate_user_integrity_error(e)

            if domain_error is not None:
                raise domain_error from e

            raise

    # checked
    @traced("users.service.update_user")
    async def update_user(
        self,
        current_user_id: int,
        payload: UpdateUserRequest,
    ) -> InternalUserWithSettings:
        try:
            async with self.uow_factory() as uow:
                update_data = payload.model_dump(exclude_unset=True)
                if not update_data:
                    raise RequestValueError(
                        message="Update body is empty",
                        failed_field="body",
                    )
                update_payload = UserUpdateData(**update_data)
                user = await uow.user_repo.update_user(
                    user_id=current_user_id,
                    payload=update_payload,
                )

                await uow.flush()

                internal_user_with_settings = InternalUserWithSettings.model_validate(
                    obj=user,
                )

                # Cached decks embed owner_username, including decks saved by others.
                affected_deck_ids = []
                if "username" in update_data:
                    affected_decks = await uow.deck_repo.get_all_by_user_id(
                        user_id=current_user_id,
                        public_only=False,
                    )
                    affected_deck_ids = [deck.id for deck in affected_decks]

                invalidation = (
                    scopes.users(internal_user_with_settings.id),
                    scopes.decks(*affected_deck_ids),
                )
                message = cache_invalidation_message(*invalidation)
                uow.outbox_repo.add(message)
                await uow.commit()

                await self.cache_invalidator.invalidate(*invalidation)
                await uow.outbox_repo.mark_published(message.id)
                await uow.commit()

                return internal_user_with_settings

        except IntegrityError as e:
            domain_error = translate_user_integrity_error(e)

            if domain_error is not None:
                raise domain_error from e

            raise

    # checked
    @traced("users.service.update_user_settings")
    async def update_user_settings(
        self,
        current_user_id: int,
        payload: UpdateUserSettingsRequest,
    ) -> InternalUserSettings:
        async with self.uow_factory() as uow:
            update_data = payload.model_dump(exclude_unset=True)
            if not update_data:
                raise RequestValueError(
                    message="Update body is empty",
                    failed_field="body",
                )
            update_payload = UserSettingsUpdateData(**update_data)
            user_settings = await uow.user_settings_repo.update_user_settings(
                user_id=current_user_id,
                payload=update_payload,
            )
            await uow.flush()

            internal_user_settings = InternalUserSettings.model_validate(
                obj=user_settings,
            )

            invalidation = (
                scopes.users_settings(internal_user_settings.user_id),
            )
            message = cache_invalidation_message(*invalidation)
            uow.outbox_repo.add(message)
            await uow.commit()

            await self.cache_invalidator.invalidate(*invalidation)
            await uow.outbox_repo.mark_published(message.id)
            await uow.commit()

            return internal_user_settings

    async def _archive_decks_after_user_deletion(
        self,
    ):
        ...

    @traced("users.service.delete_user")
    async def delete_user(
            self,
            current_user_id: int,
        ) -> None:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_id(
                user_id=current_user_id,
                for_update=True,
            )
            if user is None:
                raise UserNotFoundError()

            if user.id != current_user_id:
                raise PermissionDeniedError()

            user_id = user.id
            removed_user = scopes.users_removed(user)

            owned_decks = await uow.deck_repo.get_all_by_user_id(
                user_id=user_id,
                public_only=False,
            )
            owned_deck_ids = {deck.id for deck in owned_decks}
            owned_deck_uuids = [deck.uuid for deck in owned_decks]
            owned_card_identities = await uow.card_repo.get_identities_by_user_id(
                user_id=user_id,
            )
            owned_card_ids = [card_id for card_id, _ in owned_card_identities]
            owned_card_uuids = [card_uuid for _, card_uuid in owned_card_identities]
            linked_deck_ids = await uow.deck_card_repo.get_all_deck_ids_by_card_ids(
                card_ids=owned_card_ids,
            )
            affected_deck_ids = owned_deck_ids | set(linked_deck_ids)

            existing_user_deck_keys = set(
                await uow.user_deck_repo.get_user_deck_keys_by_deck_ids(
                    deck_ids=sorted(affected_deck_ids),
                )
            )
            removed_user_deck_keys = set(
                await uow.user_deck_repo.get_user_deck_keys_by_user_id(
                    user_id=user_id,
                )
            )
            affected_user_ids = sorted(
                set(await uow.user_deck_repo.get_library_user_ids_by_deck_ids(
                    deck_ids=sorted(affected_deck_ids),
                )) - {user_id}
            )

            archived = await DeckArchiveWorkflow(uow).archive_owner_public_decks(
                owner_id=user_id,
            )

            await uow.user_repo.delete(user)

            invalidation = (
                removed_user,
                scopes.user_decks(*sorted(
                    existing_user_deck_keys
                    | removed_user_deck_keys
                    | archived.changes.user_deck_keys
                )),
                scopes.library_deck_pages(*affected_user_ids),
                scopes.deck_with_cards(*sorted(
                    affected_deck_ids | archived.changes.deck_ids
                )),
                scopes.deck_ids_by_uuids(*owned_deck_uuids),
                scopes.cards(*owned_card_ids),
                scopes.card_ids_by_uuids(*owned_card_uuids),
            )
            message = cache_invalidation_message(*invalidation)
            uow.outbox_repo.add(message)
            await uow.commit()

            await self.cache_invalidator.invalidate(*invalidation)
            await uow.outbox_repo.mark_published(message.id)
            await uow.commit()
