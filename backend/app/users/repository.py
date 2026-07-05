from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User
from app.training_sessions.models import TrainingSession

class UserRepository():
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_uuid(self, user_uuid: UUID) -> User | None:
        stmt = select(User).where(User.uuid == user_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_by_limit(self, limit: int = 10) -> list[User]:
        stmt = select(User).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_training_sessions_by_user_uuid(
            self,
            user_uuid: UUID,
            limit: int = 10,
    ) -> list[TrainingSession]:
        stmt = select(TrainingSession).where(TrainingSession.user_uuid == user_uuid).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    def add(self, user: User) -> None:
        self.session.add(user)

    async def delete(self, user: User) -> None:
        await self.session.delete(user)

    async def refresh(self, user: User) -> None:
        await self.session.refresh(user)

    