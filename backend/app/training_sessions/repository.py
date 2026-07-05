from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.training_sessions.models import TrainingSession


class TrainingSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_uuid(self, session_uuid: UUID) -> TrainingSession | None:
        stmt = select(TrainingSession).where(TrainingSession.uuid == session_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_limit(self, limit: int = 10) -> list[TrainingSession]:
        stmt = select(TrainingSession).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_all_by_user_uuid(
        self,
        user_uuid: UUID,
        limit: int = 10,
    ) -> list[TrainingSession]:
        stmt = (
            select(TrainingSession)
            .where(TrainingSession.user_uuid == user_uuid)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_by_deck_id(
        self,
        deck_id: int,
        limit: int = 10,
    ) -> list[TrainingSession]:
        stmt = (
            select(TrainingSession)
            .where(TrainingSession.deck_id == deck_id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, training_session: TrainingSession) -> None:
        self.session.add(training_session)

    async def delete(self, training_session: TrainingSession) -> None:
        await self.session.delete(training_session)

    async def refresh(self, training_session: TrainingSession) -> None:
        await self.session.refresh(training_session)