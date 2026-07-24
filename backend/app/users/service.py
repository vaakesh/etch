from typing import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError





from app.service import UnitOfWork
from app.users.schemas import UserCreate, UserSchema, UserUpdate
from app.users.models import User
from app.users.errors import UserAlreadyExistsError, UserNotFoundError
from app.auth.utils import hash_password
from app.training_sessions.schemas import TrainingSessionSchema
from app.decks.schemas import DeckSchema, ShortDeckOut


class UserService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_user_decks(
            self,
            user_id: int,
    ) -> list[ShortDeckOut]:
        async with self.uow_factory() as uow:
            decks = await uow.deck_repo.get_all_by_user_id(
                user_id=user_id,
                limit=30,
            )
            return decks

    async def get_by_uuid(self, user_uuid: UUID) -> UserSchema:
        async with self.uow_factory() as uow:
            user = await self._get_by_uuid(uow, user_uuid)
            return user

    async def _get_by_uuid(self, uow: UnitOfWork, user_uuid: UUID) -> User:
        user = await uow.user_repo.get_by_uuid(user_uuid)
        if user is None:
            raise UserNotFoundError(f"User with uuid={user_uuid} not found")
        return user
    
    async def get_training_sessions_by_user(
            self,
            user_uuid: UUID,
            limit: int = 10,
    ) -> list[TrainingSessionSchema]:
        async with self.uow_factory() as uow:
            await self._get_by_uuid(uow, user_uuid)

            training_sessions = await uow.user_repo.get_training_sessions_by_user_uuid(
                user_uuid=user_uuid,
                limit=limit,
            )

            return [
                TrainingSessionSchema.model_validate(training_session)
                for training_session in training_sessions
            ]
    
    async def get_all_users_by_limit(self, limit: int = 10) -> list[UserSchema]:
        async with self.uow_factory() as uow:
            users = await uow.user_repo.get_all_by_limit(limit)
            return [UserSchema.model_validate(user) for user in users]

    
    async def create_user(
            self,
            payload: UserCreate,
    ) -> UserSchema:
        try:
            async with self.uow_factory() as uow:
                user_data = payload.model_dump(exclude={"password"})
                user = User(
                    **user_data,
                    hashed_password=hash_password(payload.password),
                )
                uow.user_repo.add(user)
                await uow.commit()
                await uow.user_repo.refresh(user)
                return UserSchema.model_validate(user)
        except IntegrityError as e:
            raise UserAlreadyExistsError() from e
        
    async def update_user(
            self,
            user_uuid: UUID,
            payload: UserUpdate,
    ) -> UserSchema:
        try:
            async with self.uow_factory() as uow:
                user = await self._get_by_uuid(uow, user_uuid)

                update_data = payload.model_dump(exclude_unset=True)

                if "password" in update_data:
                    password = update_data.pop("password")
                    user.hashed_password = hash_password(password)

                for field, value in update_data.items():
                    setattr(user, field, value)

                await uow.commit()
                await uow.user_repo.refresh(user)

                return UserSchema.model_validate(user)
        except IntegrityError as e:
            raise UserAlreadyExistsError() from e
        
    async def delete_user(self, user_uuid: UUID) -> None:
        async with self.uow_factory() as uow:
            user = await self._get_by_uuid(uow, user_uuid)

            await uow.user_repo.delete(user)
            await uow.commit()

            return None
        