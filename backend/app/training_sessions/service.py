from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.service import UnitOfWork

from app.training_sessions.errors import (
    CardAlreadyAnsweredError,
    TrainingSessionAlreadyExistsError,
    TrainingSessionAlreadyFinishedError,
    TrainingSessionItemNotFoundError,
    TrainingSessionNotFoundError,
)
from app.training_sessions.models import TrainingSession
from app.training_sessions.schemas import (
    SubmitAnswerResponse,
    TrainingSessionCreate,
    TrainingSessionFinish,
    TrainingSessionSchema,
    TrainingSessionUpdate,
    UserAnswer,
)
from app.utils import utcnow


class TrainingSessionService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def submit_answer(
            self,
            user_id: int,
            training_session_uuid: UUID,
            sequence_number: int,
            user_answer: UserAnswer,
    ) -> SubmitAnswerResponse:
        async with self.uow_factory() as uow:
            training_session = await uow.training_session_repo.get_by_uuid(
                training_session_uuid,
                for_update=True,
            )

            if training_session is None or training_session.user_id != user_id:
                raise TrainingSessionNotFoundError()

            item = await uow.training_session_item_repo.get_item_by_sequence_number_and_session_id(
                training_session_id=training_session.id,
                sequence_number=sequence_number,
                for_update=True,
            )

            if item is None:
                raise TrainingSessionItemNotFoundError()

            if item.is_answered:
                response = SubmitAnswerResponse(
                    is_correct=item.is_correct, 
                    answer_text=item.answer_text,
                    answered_count=training_session.actual_count,
                    correct_count=training_session.correct_count,
                    total_count=training_session.requested_count,
                    is_finished=True if training_session.finished_at else False,
                    time_to_complete=(
                        int((training_session.finished_at - training_session.started_at).total_seconds())
                        if training_session.finished_at
                        else None
                    ),
                )
                return response

            if training_session.finished_at is not None:
                raise TrainingSessionAlreadyFinishedError()

            item.is_answered = True
            item.answered_at = utcnow()
            training_session.actual_count += 1
        
            if user_answer.action == "answer" and user_answer.answer.lower().strip() == item.answer_text.lower().strip():
                training_session.correct_count += 1
                item.is_correct = True
            else:
                item.is_correct = False
                training_session.wrong_count += 1

            if training_session.actual_count == training_session.requested_count and training_session.finished_at is None:
                training_session.finished_at = utcnow()
                await self._update_user_deck_after_session(
                        uow=uow,
                        user_id=user_id,
                        training_session=training_session,
                    )

            response = SubmitAnswerResponse(
                    is_correct=item.is_correct, 
                    answer_text=item.answer_text,
                    answered_count=training_session.actual_count,
                    correct_count=training_session.correct_count,
                    total_count=training_session.requested_count,
                    is_finished=True if training_session.finished_at else False,
                    time_to_complete=(
                        int((training_session.finished_at - training_session.started_at).total_seconds())
                        if training_session.finished_at
                        else None
                    ),
                )

            await uow.commit()
            
            return response

    async def _update_user_deck_after_session(
        self,
        uow: UnitOfWork,
        user_id: int,
        training_session: TrainingSession,
    ):
        user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
            user_id=user_id,
            deck_id=training_session.deck_id,
            for_update=True,
        )

        user_deck.sessions_count += 1
        user_deck.correct_count += training_session.correct_count
        user_deck.wrong_count += training_session.wrong_count
        user_deck.last_studied_at = training_session.finished_at

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
            user = await uow.user_repo.get_by_uuid(user_uuid=user_uuid)
            training_sessions = await uow.training_session_repo.get_all_by_user_id(
                user_id=user.id,
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

    async def delete_training_session(self, session_uuid: UUID) -> None:
        async with self.uow_factory() as uow:
            training_session = await self._get_by_uuid(uow, session_uuid)

            await uow.training_session_repo.delete(training_session)
            await uow.commit()

            return None