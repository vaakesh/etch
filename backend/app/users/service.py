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
from app.users.models import User
from app.users.schemas import UserCreate, UserUpdate
from sqlalchemy.exc import IntegrityError


class UserService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_by_uuid(
            self, 
            user_uuid: UUID,
            for_update: bool = False,
        ) -> User:
        async with self.uow_factory() as uow:
            user = await self._get_by_uuid(
                uow=uow, 
                user_uuid=user_uuid,
                for_update=for_update,
            )
            return user

    async def _get_by_uuid(
            self, 
            uow: UnitOfWork, 
            user_uuid: UUID,
            for_update: bool = False,
        ) -> User:
        user = await uow.user_repo.get_by_uuid(
            user_uuid=user_uuid,
            for_update=for_update,
        )
        if user is None:
            raise UserNotFoundError(f"User with uuid={user_uuid} not found")
        return user
    
    async def create_user(
            self,
            payload: UserCreate,
    ) -> User:
        try:
            async with self.uow_factory() as uow:
                user_data = payload.model_dump(exclude={"password"})
                user = User(
                    **user_data,
                    hashed_password=hash_password(payload.password),
                )
                uow.user_repo.add(user)
                await uow.commit()
                return user
        except IntegrityError as e:
            raise UserAlreadyExistsError() from e
        
    async def update_user(
            self,
            target_user_uuid: UUID,
            current_user_id: int,
            payload: UserUpdate,
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
                )

                if target_user.id != current_user_id:
                    raise PermissionDeniedError()

                for field, value in update_data.items():
                    setattr(target_user, field, value)

                await uow.flush()
                await uow.user_repo.refresh(target_user)
                await uow.commit()

                return target_user
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
        