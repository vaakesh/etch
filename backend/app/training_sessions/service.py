from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.service import UnitOfWork

from app.training_sessions.errors import (
    TrainingSessionAlreadyExistsError,
    TrainingSessionNotFoundError,
)
from app.training_sessions.models import TrainingSession
from app.training_sessions.schemas import (
    TrainingSessionCreate,
    TrainingSessionFinish,
    TrainingSessionSchema,
    TrainingSessionUpdate,
)


class TrainingSessionService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_by_uuid(self, session_uuid: UUID) -> TrainingSessionSchema:
        async with self.uow_factory() as uow:
            training_session = await self._get_by_uuid(uow, session_uuid)
            return TrainingSessionSchema.model_validate(training_session)

    async def _get_by_uuid(
        self,
        uow: UnitOfWork,
        session_uuid: UUID,
    ) -> TrainingSession:
        training_session = await uow.training_session_repo.get_by_uuid(session_uuid)

        if training_session is None:
            raise TrainingSessionNotFoundError(
                f"Training session with uuid={session_uuid} not found"
            )

        return training_session

    async def get_all_training_sessions_by_limit(
        self,
        limit: int = 10,
    ) -> list[TrainingSessionSchema]:
        async with self.uow_factory() as uow:
            training_sessions = await uow.training_session_repo.get_all_by_limit(limit)
            return [
                TrainingSessionSchema.model_validate(training_session)
                for training_session in training_sessions
            ]
        
    async def get_all_by_user_uuid(
        self,
        user_uuid: UUID,
        limit: int = 10,
    ) -> list[TrainingSessionSchema]:
        async with self.uow_factory() as uow:
            training_sessions = await uow.training_session_repo.get_all_by_user_uuid(
                user_id=user_uuid,
                limit=limit,
            )
            return [
                TrainingSessionSchema.model_validate(training_session)
                for training_session in training_sessions
            ]

    async def get_all_by_deck_id(
        self,
        deck_id: int,
        limit: int = 10,
    ) -> list[TrainingSessionSchema]:
        async with self.uow_factory() as uow:
            training_sessions = await uow.training_session_repo.get_all_by_deck_id(
                deck_id=deck_id,
                limit=limit,
            )
            return [
                TrainingSessionSchema.model_validate(training_session)
                for training_session in training_sessions
            ]

    async def create_training_session(
        self,
        payload: TrainingSessionCreate,
    ) -> TrainingSessionSchema:
        try:
            async with self.uow_factory() as uow:
                training_session = TrainingSession(
                    **payload.model_dump(),
                )

                uow.training_session_repo.add(training_session)

                await uow.commit()
                await uow.training_session_repo.refresh(training_session)

                return TrainingSessionSchema.model_validate(training_session)

        except IntegrityError as e:
            raise TrainingSessionAlreadyExistsError() from e

    async def update_training_session(
        self,
        session_uuid: UUID,
        payload: TrainingSessionUpdate,
    ) -> TrainingSessionSchema:
        try:
            async with self.uow_factory() as uow:
                training_session = await self._get_by_uuid(uow, session_uuid)

                update_data = payload.model_dump(exclude_unset=True)

                for field, value in update_data.items():
                    setattr(training_session, field, value)

                await uow.commit()
                await uow.training_session_repo.refresh(training_session)

                return TrainingSessionSchema.model_validate(training_session)

        except IntegrityError as e:
            raise TrainingSessionAlreadyExistsError() from e

    async def finish_training_session(
        self,
        session_uuid: UUID,
        payload: TrainingSessionFinish,
    ) -> TrainingSessionSchema:
        async with self.uow_factory() as uow:
            training_session = await self._get_by_uuid(uow, session_uuid)

            training_session.correct_count = payload.correct_count
            training_session.wrong_count = payload.wrong_count
            training_session.score = payload.score
            training_session.finished_at = datetime.now(timezone.utc)

            await uow.commit()
            await uow.training_session_repo.refresh(training_session)

            return TrainingSessionSchema.model_validate(training_session)

    async def delete_training_session(self, session_uuid: UUID) -> None:
        async with self.uow_factory() as uow:
            training_session = await self._get_by_uuid(uow, session_uuid)

            await uow.training_session_repo.delete(training_session)
            await uow.commit()

            return None