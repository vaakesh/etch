from collections.abc import Callable
import logging
from uuid import UUID

from asyncpg import UniqueViolationError

from app.auth.utils import hash_password
from app.errors import RequestValueError
from app.service import UnitOfWork
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
from app.common.types import Username

logger = logging.getLogger(__name__)

class UserService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service

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
    async def create_user(
            self,
            payload: CreateUserRequest,
    ) -> InternalUserWithSettings:
        try:
            async with self.uow_factory() as uow:
                user_data = payload.model_dump(exclude={"password"})
                user = User(
                    **user_data,
                    hashed_password=hash_password(payload.password),
                )
                uow.user_repo.add(user)
                await uow.flush()
                user_settings = UserSettings(
                    user_id=user.id,
                    locale="ru-RU",
                    theme="system",
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

                await uow.commit()

                await self.cache_service.invalidate_users(
                    user_ids=[internal_user_with_settings.id],
                )

                return internal_user_with_settings

        except IntegrityError as e:
            domain_error = translate_user_integrity_error(e)

            if domain_error is not None:
                raise domain_error from e

            raise

    # checked
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

            await uow.commit()

            await self.cache_service.invalidate_users_settings(
                user_ids=[user_settings.user_id],
            )
            
            return internal_user_settings

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

            user_uuid = user.uuid
            user_id = user.id

            affected_decks = await uow.deck_repo.get_all_by_user_id(
                user_id=user_id,
                public_only=False,
            )

            existing_user_deck_keys = set(
                await uow.user_deck_repo.get_user_deck_keys_by_deck_ids(
                    deck_ids=[deck.id for deck in affected_decks]
                )
            )

            archived = await DeckArchiveWorkflow(uow).archive_owner_public_decks(
                owner_id=user_id,
            )
            affected_user_ids = sorted(
                {user_id for user_id, _ in existing_user_deck_keys}
                | set(archived.recipient_ids)
                | {user_id}
            )

            await uow.user_repo.delete(user)
            await uow.commit()

            # invalidation
            await self.cache_service.invalidate_user_decks(
                identities=list(
                    existing_user_deck_keys | archived.changes.user_deck_keys
                ),
            )
            await self.cache_service.invalidate_user_ids_by_uuids(
                user_uuids=[user_uuid],
            )
            await self.cache_service.invalidate_users(
                user_ids=[user_id],
            )
            await self.cache_service.invalidate_users_settings(
                user_ids=[user_id],
            )
            await self.cache_service.invalidate_library_deck_pages(
                user_ids=affected_user_ids,
            )
            await self.cache_service.invalidate_library_card_pages(
                user_ids=affected_user_ids,
            )
            await self.cache_service.invalidate_decks(
                deck_ids=list(
                    {deck.id for deck in affected_decks} | archived.changes.deck_ids
                ),
            )
            await self.cache_service.invalidate_deck_cards(
                deck_ids=[deck.id for deck in affected_decks],
            )
            await self.cache_service.invalidate_cards(
                card_ids=list(archived.changes.card_ids),
            )
