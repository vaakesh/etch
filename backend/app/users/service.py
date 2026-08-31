from collections.abc import Callable
from uuid import UUID

from app.auth.utils import hash_password
from app.errors import RequestValueError
from app.service import UnitOfWork
from app.users.errors import (
    PermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.users.models import User, UserSettings
from app.users.schemas import CreateUserRequest, InternalUser, InternalUserSettings, InternalUserWithSettings, PrivateUserResponse, UserSettingsUpdate, UpdateUserRequest
from sqlalchemy.exc import IntegrityError

from app.redis.service import RedisCacheService


class UserService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service

    async def get_user_settings_by_id(
        self,
        user_id: int,
        for_update: bool = False,
    ) -> InternalUserSettings:
        if not for_update:
            settings_lookup = await self.cache_service.get_cached_users_settings(
                user_ids=[user_id],
            )
            cached_user_settings = settings_lookup.cached.get(user_id)
            if cached_user_settings is not None:
                return cached_user_settings

        async with self.uow_factory() as uow:
            user_settings = await uow.user_settings_repo.get_by_user_id(
                user_id=user_id,
                for_update=for_update,
            )
            internal_user_settings = InternalUserSettings.model_validate(
                obj=user_settings,
            )
            if not for_update:
                await self.cache_service.cache_users_settings(
                    users_settings=[internal_user_settings],
                )
            return internal_user_settings

    async def _get_user_settings_by_id(
            self,
            uow: UnitOfWork,
            user_id: int,
            for_update: bool = False,
        ) -> UserSettings:
            user_settings = await uow.user_settings_repo.get_by_user_id(
                user_id=user_id,
                for_update=for_update,
            )
            if user_settings is None:
                raise UserNotFoundError()
            return user_settings

    async def get_by_uuid_with_settings(
        self,
        user_uuid: UUID,
    ) -> InternalUserWithSettings:
        id_lookup = await self.cache_service.get_cached_ids_by_uuids(
            user_uuids=[user_uuid],
        )
        cached_id = id_lookup.cached.get(user_uuid)
        if cached_id is not None:
            user_lookup = await self.cache_service.get_cached_users(
                user_ids=[cached_id],
            )
            user_settings_lookup = (
                await self.cache_service.get_cached_users_settings(
                    user_ids=[cached_id],
                )
            )

            cached_user = user_lookup.cached.get(cached_id)
            cached_user_settings = (
                user_settings_lookup.cached.get(cached_id)
            )
            if (
                cached_user is not None 
                and cached_user_settings is not None
                and cached_user.uuid == user_uuid
            ):
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
            await self.cache_service.cache_user_ids_by_uuids(
                user_uuids=[internal_user.uuid],
                user_ids=[internal_user.id],
            )

            return InternalUserWithSettings.from_parts(
                user=internal_user,
                settings=internal_user_settings,
            )
        

    async def get_by_uuid(
        self,
        user_uuid: UUID,
        for_update: bool = False,
    ) -> InternalUser:
        if not for_update:
            id_lookup = await self.cache_service.get_cached_ids_by_uuids(
                user_uuids=[user_uuid],
            )

            cached_id = id_lookup.cached.get(user_uuid)

            if cached_id is not None:
                user_lookup = await self.cache_service.get_cached_users(
                    user_ids=[cached_id],
                )

                cached_user = user_lookup.cached.get(cached_id)

                if cached_user is not None and cached_user.uuid == user_uuid:
                    return cached_user

        async with self.uow_factory() as uow:
            user = await self._get_by_uuid(
                uow=uow,
                user_uuid=user_uuid,
                for_update=for_update,
                get_settings=False,
            )

            internal_user = InternalUser.model_validate(obj=user)

            if not for_update:
                await self.cache_service.cache_user_ids_by_uuids(
                    user_uuids=[internal_user.uuid],
                    user_ids=[internal_user.id],
                )
                await self.cache_service.cache_users(
                    users=[internal_user],
                )

            return internal_user

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
            get_settings=get_settings,
        )
        if user is None:
            raise UserNotFoundError(f"User with uuid={user_uuid} not found")
        return user
    
    async def create_user(
            self,
            payload: CreateUserRequest,
    ) -> tuple[InternalUser, InternalUserSettings]:
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
                    theme="light",
                    show_previews_for_long=True,
                )
                uow.user_settings_repo.add(user_settings)
                await uow.commit()
                await uow.user_settings_repo.refresh(user_settings)
                return (
                    InternalUser.model_validate(obj=user), 
                    InternalUserSettings.model_validate(obj=user_settings)
                )
        except IntegrityError as e:
            raise UserAlreadyExistsError() from e

    async def update_user_settings(
        self,
        current_user_id: int,
        payload: UserSettingsUpdate,
    ) -> UserSettings:
        async with self.uow_factory() as uow:
            update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
            if not update_data:
                raise RequestValueError(
                    message="Update body is empty",
                    failed_field="body",
                )

            user_settings = await self._get_user_settings_by_id(
                uow=uow,
                user_id=current_user_id,
                for_update=True,
            )
            user_id = user_settings.user_id

            for field, value in update_data.items():
                setattr(user_settings, field, value)

            await uow.flush()
            await uow.user_settings_repo.refresh(user_settings)
            await uow.commit()

            await self.cache_service.invalidate_users_settings(
                user_ids=[user_id],
            )
            
            internal_user_settings = InternalUserSettings.model_validate(
                obj=user_settings,
            )
            return internal_user_settings

    async def update_user(
            self,
            target_user_uuid: UUID,
            current_user_id: int,
            payload: UpdateUserRequest,
    ) -> InternalUserWithSettings:
        try:
            async with self.uow_factory() as uow:
                update_data = payload.model_dump(exclude_unset=True, exclude_none=True)

                if not update_data:
                    raise RequestValueError(
                        message="Update body is empty",
                        failed_field="body",
                    )
                
                target_user = await self._get_by_uuid(
                    uow=uow,
                    user_uuid=target_user_uuid,
                    for_update=True,
                    get_settings=True,
                )

                if target_user.id != current_user_id:
                    raise PermissionDeniedError()

                for field, value in update_data.items():
                    setattr(target_user, field, value)

                await uow.flush()
                await uow.user_repo.refresh(target_user)
                await uow.commit()

                internal_user_with_settings = InternalUserWithSettings.from_parts(
                    user=InternalUser.model_validate(obj=target_user),
                    settings=InternalUserSettings.model_validate(
                        obj=target_user.settings,
                    )
                )

                # invalidation
                await self.cache_service.invalidate_user_ids_by_uuids(
                    user_uuids=[internal_user_with_settings.uuid],
                )
                await self.cache_service.invalidate_users(
                    user_ids=[internal_user_with_settings.id],
                )

                return internal_user_with_settings

        except IntegrityError as e:
            raise UserAlreadyExistsError() from e
        
    async def delete_user(
            self,
            current_user_id: int,
            target_user_uuid: UUID,
        ) -> None:
        async with self.uow_factory() as uow:
            user = await self._get_by_uuid(
                uow, 
                target_user_uuid,
                for_update=True,
            )
            if user.id != current_user_id:
                raise PermissionDeniedError()

            user_uuid = user.uuid
            user_id = user.id

            await uow.user_repo.delete(user)
            await uow.commit()

            # invalidation
            await self.cache_service.invalidate_user_ids_by_uuids(
                user_uuids=[user_uuid],
            )
            await self.cache_service.invalidate_users(
                user_ids=[user_id],
            )
            await self.cache_service.invalidate_users_settings(
                user_ids=[user_id],
            )


            return None
        