import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.bff.schemas import UserProgressResponse
from app.common.types import PositiveInt
from app.common.utils import decode_cursor, encode_cursor, utcnow
from app.decks.errors import DeckIsEmptyError, DeckNotFoundError, UserDeckNotFoundError
from app.decks.models import UserDeck
from app.redis.service import RedisCacheService
from app.service import UnitOfWork
from app.training_sessions.errors import (
    TrainingSessionAlreadyFinishedError,
    TrainingSessionItemNotFoundError,
    TrainingSessionNotFinishedYet,
    TrainingSessionNotFoundError,
)
from app.training_sessions.models import TrainingSession, TrainingSessionItem
from app.training_sessions.schemas import (
    InternalTrainingSession,
    InternalTrainingSessionItem,
    PracticeCardResponse,
    PracticeSessionResponse,
    SubmitAnswerResponse,
    TrainingSessionStatus,
)
from app.training_sessions.types import UserAnswer
from app.users.errors import UserNotFoundError

logger = logging.getLogger(__name__)

class TrainingSessionService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service


    async def user_daily_activity(
        self,
        user_id: int,
        from_date: datetime,
        to_date: datetime | None,
    ) -> dict[date: int]:
        async with self.uow_factory() as uow:
            result = await uow.training_session_item_repo.get_user_daily_activity(
                user_id=user_id,
                from_date=from_date,
                to_date=to_date,
            )
            count_by_day: dict[date: int] = defaultdict(int)
            for id, id_datetime in result:
                count_by_day[id_datetime.date()] += 1
            return count_by_day

    async def get_user_progress(
        self,
        user_id: int,
    ) -> UserProgressResponse:
        async with self.uow_factory() as uow:
            return await uow.training_session_item_repo.get_user_progress(
                user_id=user_id,
            )

    async def get_session_history(
        self,
        user_id: int,
        session_uuid: UUID,
        only_answered_items: bool = False,
        page_size: int = 30,
        page_number: int = 1,
    ) -> list[InternalTrainingSessionItem] | None:
        async with self.uow_factory() as uow:

            rows = await uow.training_session_item_repo.get_session_history(
                user_id=user_id,
                session_uuid=session_uuid,
                last_sequence_number=(
                    page_size * (page_number - 1)
                ),
                page_size=page_size,
                only_answered_items=only_answered_items,
            )
            if not rows:
                raise TrainingSessionNotFoundError()
            items: list[InternalTrainingSessionItem] = []
            status = rows[0][1]
            for item, _ in rows:
                if item is not None:
                    items.append(InternalTrainingSessionItem.model_validate(obj=item))

            if status == TrainingSessionStatus.IN_PROGRESS:
                raise TrainingSessionNotFinishedYet()

            return items

    async def submit_answer(
            self,
            user_id: int,
            training_session_uuid: UUID,
            sequence_number: int,
            user_answer: UserAnswer,
    ) -> SubmitAnswerResponse:
        async with self.uow_factory() as uow:
            user_deck_changed = False
            training_session = await uow.training_session_repo.get_by_uuid(
                training_session_uuid,
                for_update=True,
            )

            if training_session is None or training_session.user_id != user_id:
                raise TrainingSessionNotFoundError()

            item = (
                await uow.training_session_item_repo
                .get_item_by_sequence_number_and_session_id(
                    training_session_id=training_session.id,
                    sequence_number=sequence_number,
                    for_update=True,
                )
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
                        int((training_session.finished_at - training_session.started_at)
                            .total_seconds())
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
        
            if (
                user_answer.action == "answer" 
                and 
                user_answer.answer.lower().strip() == item.answer_text.lower().strip()
            ):
                training_session.correct_count += 1
                item.is_correct = True
            else:
                item.is_correct = False
                training_session.wrong_count += 1

            if user_answer.action == "answer":
                item.user_typed_text = user_answer.answer

            # в статистику идут только завершенные сессии
            if (
                training_session.actual_count == training_session.requested_count 
                and 
                training_session.finished_at is None
            ):
                training_session.finished_at = utcnow()
                training_session.status = TrainingSessionStatus.COMPLETED
                await self._update_user_deck_after_session(
                        uow=uow,
                        user_id=user_id,
                        training_session=training_session,
                    )
                user_deck_changed = True

            response = SubmitAnswerResponse(
                    is_correct=item.is_correct, 
                    answer_text=item.answer_text,
                    answered_count=training_session.actual_count,
                    correct_count=training_session.correct_count,
                    total_count=training_session.requested_count,
                    is_finished=True if training_session.finished_at else False,
                    time_to_complete=(
                        int((training_session.finished_at - training_session.started_at)
                            .total_seconds())
                        if training_session.finished_at
                        else None
                    ),
                )

            await uow.commit()

            if user_deck_changed:
                await self.cache_service.invalidate_user_decks(
                    identities=[(training_session.user_id, training_session.deck_id)],
                )
            
            return response

    async def _update_user_deck_after_session(
        self,
        uow: UnitOfWork,
        user_id: int,
        training_session: TrainingSession,
    ) -> None:
        user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
            user_id=user_id,
            deck_id=training_session.deck_id,
            for_update=True,
        )
        if user_deck is None:
            raise UserDeckNotFoundError()

        if training_session.finished_at:
            user_deck.sessions_count += 1
            user_deck.correct_count += training_session.correct_count
            user_deck.wrong_count += training_session.wrong_count
            user_deck.last_studied_at = training_session.finished_at

    async def get_by_uuid(
            self, 
            session_uuid: UUID,
            current_user_id: int | None = None,
        ) -> InternalTrainingSession:
        async with self.uow_factory() as uow:
            training_session = await self._get_by_uuid(uow, session_uuid)

            # только завершенные сессии в публичный доступ
            if training_session.status != TrainingSessionStatus.COMPLETED:
                if current_user_id is None or current_user_id != training_session.user_id:
                    raise TrainingSessionNotFoundError()
            
            return InternalTrainingSession.model_validate(training_session)

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
        
    async def get_all_by_user_uuid(
        self,
        user_uuid: UUID,
        status: TrainingSessionStatus | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> tuple[list[InternalTrainingSession], str | None, bool]:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_uuid(
                user_uuid=user_uuid,
                for_update=False,
            )
            if user is None:
                raise UserNotFoundError()

            next_cursor = None

            match status:
                case TrainingSessionStatus.COMPLETED | TrainingSessionStatus.ABANDONED:
                    cursor_finished_at, cursor_id = (
                        decode_cursor(cursor) if cursor is not None 
                        else (None, None)
                    )
                    training_sessions, has_more = (
                        await uow.training_session_repo
                        .get_all_finished_sessions_by_user_id(
                            user_id=user.id,
                            status=status,
                            cursor_finished_at=cursor_finished_at,
                            cursor_id=cursor_id,
                            limit=limit,
                        )
                    )
                    if has_more and training_sessions:
                        next_cursor = encode_cursor(
                            training_sessions[-1].finished_at,
                            training_sessions[-1].id,
                        )
                case TrainingSessionStatus.IN_PROGRESS:
                    cursor_started_at, cursor_id = (
                        decode_cursor(cursor) if cursor is not None 
                        else (None, None)
                    )
                    training_sessions, has_more = (
                        await uow.training_session_repo
                        .get_all_unfinished_sessions_by_user_id(
                            user_id=user.id,
                            cursor_started_at=cursor_started_at,
                            cursor_id=cursor_id,
                            limit=limit,
                        )
                    )
                    if has_more and training_sessions:
                        next_cursor = encode_cursor(
                            training_sessions[-1].started_at,
                            training_sessions[-1].id,
                        )
                case None:
                    cursor_started_at, cursor_id = (
                        decode_cursor(cursor) if cursor is not None 
                        else (None, None)
                    )
                    training_sessions, has_more = (
                        await uow.training_session_repo.get_all_sessions_by_user_id(
                            user_id=user.id,
                            cursor_started_at=cursor_started_at,
                            cursor_id=cursor_id,
                            limit=limit,
                        )
                    )
                    if has_more and training_sessions:
                        next_cursor = encode_cursor(
                            training_sessions[-1].started_at,
                            training_sessions[-1].id,
                        )
            
            return (
                [
                    InternalTrainingSession.model_validate(training_session)
                    for training_session in training_sessions
                ],
                next_cursor,
                has_more
            )

    async def start_training_session(
        self,
        user_id: int,
        deck_uuid: UUID,
        words_per_session: PositiveInt,
        prompt_side: Literal["front", "back"],
    ) -> PracticeSessionResponse:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(
                deck_uuid=deck_uuid,
                for_update=True,
            )

            if deck is None:
                raise DeckNotFoundError()

            if deck.user_id != user_id and not deck.is_public:
                raise DeckNotFoundError()

            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
            )

            if user_deck is None:
                user_deck = UserDeck(
                    user_id=user_id,
                    deck_id=deck.id,
                    sessions_count=0,
                    correct_count=0,
                    wrong_count=0,
                    last_seen_version=deck.version,
                )
                uow.user_deck_repo.add(user_deck)

            answer_side = "back" if prompt_side == "front" else "front"

            training_session = TrainingSession(
                user_id=user_id,
                deck_id=deck.id,
                requested_count=words_per_session,
                actual_count=0,
                correct_count=0,
                wrong_count=0,
                prompt_side=prompt_side,
                answer_side=answer_side,
            )
            uow.training_session_repo.add(training_session)

            await uow.flush()

            training_session_items = await uow.training_session_item_repo.create_snapshot(
                training_session_id=training_session.id,
                deck_id=deck.id,
                prompt_side=prompt_side,
                answer_side=answer_side,
                words_per_session=words_per_session,
            )
            if not training_session_items:
                raise DeckIsEmptyError()

            training_session.requested_count = len(training_session_items)

            response = PracticeSessionResponse(
                training_session_uuid=training_session.uuid,
                deck_uuid=deck.uuid,
                prompt_side=training_session.prompt_side,
                answer_side=training_session.answer_side,
                total_count=training_session.requested_count,
                answered_count=training_session.actual_count,
                correct_count=training_session.correct_count,
                wrong_count=training_session.wrong_count,
                started_at=training_session.started_at,
                cards=[PracticeCardResponse(
                    sequence_number=item.sequence_number,
                    prompt_text=item.prompt_text,
                    prompt_language=item.prompt_lang,
                    answer_language=item.answer_lang,
                ) for item in training_session_items]
            )

            await uow.commit()

            return response

    async def resume_practice_session(
            self,
            user_id: int,
            training_session_uuid: UUID,
    ) -> PracticeSessionResponse:
        async with self.uow_factory() as uow:
            training_session = await uow.training_session_repo.get_by_uuid(
                training_session_uuid,
            )

            if training_session is None or training_session.user_id != user_id:
                raise TrainingSessionNotFoundError()

            if training_session.finished_at is not None:
                raise TrainingSessionAlreadyFinishedError()

            deck = await uow.deck_repo.get_by_id(training_session.deck_id)

            if deck is None:
                raise DeckNotFoundError()

            training_session_next_cards = (
                await uow.training_session_item_repo.get_next_cards(
                    training_session_id=training_session.id,
                )
            )

            return PracticeSessionResponse(
                training_session_uuid=training_session.uuid,
                deck_uuid=deck.uuid,
                prompt_side=training_session.prompt_side,
                answer_side=training_session.answer_side,
                total_count=training_session.requested_count,
                answered_count=training_session.actual_count,
                correct_count=training_session.correct_count,
                wrong_count=training_session.wrong_count,
                started_at=training_session.started_at,
                cards=[PracticeCardResponse(
                    sequence_number=item.sequence_number,
                    prompt_text=item.prompt_text,
                    prompt_language=item.prompt_lang,
                    answer_language=item.answer_lang,
                ) for item in training_session_next_cards]
            )
