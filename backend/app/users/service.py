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
from app.users.schemas import CreateUserRequest, InternalUser, UserSettingsUpdate, UpdateUserRequest
from sqlalchemy.exc import IntegrityError


class UserService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_user_settings_by_id(
        self,
        user_id: int,
        for_update: bool = False,
    ) -> UserSettings:
        async with self.uow_factory() as uow:
            user_settings = await uow.user_settings_repo.get_by_user_id(
                user_id=user_id,
                for_update=for_update,
            )
            return user_settings

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

    async def get_by_uuid(
            self, 
            user_uuid: UUID,
            for_update: bool = False,
        ) -> InternalUser:
        async with self.uow_factory() as uow:
            user = await self._get_by_uuid(
                uow=uow, 
                user_uuid=user_uuid,
                for_update=for_update,
            )
            return InternalUser.model_validate(obj=user)

    async def _get_by_uuid(
            self, 
            uow: UnitOfWork, 
            user_uuid: UUID,
            for_update: bool = False,
            get_settings: bool = True,
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
    ) -> tuple[User, UserSettings]:
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
                return InternalUser.model_validate(obj=user), user_settings
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

            for field, value in update_data.items():
                setattr(user_settings, field, value)

            await uow.flush()
            await uow.user_settings_repo.refresh(user_settings)
            await uow.commit()
            return user_settings

    async def update_user(
            self,
            target_user_uuid: UUID,
            current_user_id: int,
            payload: UpdateUserRequest,
    ) -> User:
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

                return InternalUser.model_validate(obj=target_user)
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

            await uow.user_repo.delete(user)
            await uow.commit()

            return None
        