import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID
import uuid

from app.bff.schemas import DailyActivityResponse, UserProgressResponse
from app.common.types import PositiveInt, SessionSize
from app.common.utils import decode_cursor, encode_cursor, utcnow
from app.decks.errors import DeckIsEmptyError, DeckNotFoundError, UserDeckNotFoundError
from app.decks.models import UserDeck
from app.errors import RequestValueError
from app.redis.service import RedisCacheService
from app.service import UnitOfWork
from app.training_sessions.errors import (
    PermissionDeniedError,
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
    TrainingSessionActivityRequest,
    TrainingSessionActivityResponse,
    TrainingSessionStatus,
)
from app.training_sessions.types import UserAnswer
from app.training_sessions.utils import pick_random_positions
from app.users.errors import UserNotFoundError
from app.decks.schemas import DeckLoad

logger = logging.getLogger(__name__)

class TrainingSessionService:
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
        session_uuid: UUID,
        for_update: bool = False,
    ) -> TrainingSession:
        training_session = await uow.training_session_repo.get_by_uuid(
            session_uuid=session_uuid,
            for_update=for_update,
        )

        if training_session is None:
            raise TrainingSessionNotFoundError(
                f"Training session with uuid={session_uuid} not found"
            )

        return training_session

    def _accrue_activity(
        self,
        training_session: TrainingSession,
        now: datetime,
    ) -> None:
        if (
            training_session.activity_last_seen_at is None
            or
            training_session.activity_tracker_uuid is None
        ):
            return

        gap_ms = round((
            now - training_session.activity_last_seen_at
        ).total_seconds() * 1000)

        if 0 < gap_ms <= 30_000:
            training_session.active_study_time_ms += gap_ms

        training_session.activity_last_seen_at = now

    async def _update_user_deck_after_session(
        self,
        uow: UnitOfWork,
        user_id: int,
        training_session: TrainingSession,
    ) -> None:
        if training_session.deck_id is None:
            return
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

    # read
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

            training_session_next_cards = (
                await uow.training_session_item_repo.get_next_cards(
                    training_session_id=training_session.id,
                )
            )

            return PracticeSessionResponse(
                training_session_uuid=training_session.uuid,
                deck_uuid=training_session.deck_uuid,
                prompt_side=training_session.prompt_side,
                answer_side=training_session.answer_side,
                total_count=training_session.requested_count,
                answered_count=training_session.answered_count,
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
            if status == TrainingSessionStatus.IN_PROGRESS:
                raise TrainingSessionNotFinishedYet()

            for item, _ in rows:
                if item is not None:
                    items.append(
                        InternalTrainingSessionItem.model_validate(
                            obj=item
                        )
                    )

            return items

    async def get_sessions_by_user_uuid(
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

            cursor_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None
                else (None, None)
            )
            next_cursor = None

            match status:
                case TrainingSessionStatus.COMPLETED | TrainingSessionStatus.ABANDONED:
                    sessions, has_more = (
                        await uow.training_session_repo.get_sessions_by_user_id(
                            user_id=user.id,
                            status=status,
                            cursor_at=cursor_at,
                            cursor_id=cursor_id,
                            limit=limit,
                            order_by="finished_at",
                        )
                    )
                    if has_more and sessions:
                        next_cursor = encode_cursor(
                            time_condition=(
                                sessions[-1].finished_at
                            ),
                            entity_id=(
                                sessions[-1].id
                            )
                        )
                case TrainingSessionStatus.IN_PROGRESS | None:
                    sessions, has_more = (
                        await uow.training_session_repo.get_sessions_by_user_id(
                            user_id=user.id,
                            status=status,
                            cursor_at=cursor_at,
                            cursor_id=cursor_id,
                            limit=limit,
                            order_by="started_at",
                        )
                    )
                    if has_more and sessions:
                        next_cursor = encode_cursor(
                            time_condition=(
                                sessions[-1].started_at
                            ),
                            entity_id=(
                                sessions[-1].id
                            )
                        )

            return (
                [
                    InternalTrainingSession.model_validate(session)
                    for session in sessions
                ],
                next_cursor,
                has_more
            )

    async def get_user_activity(
        self,
        user_id: int,
        from_datetime: datetime,
        to_datetime: datetime | None,
    ) -> dict[date, int]:
        async with self.uow_factory() as uow:
            return await uow.training_session_item_repo.get_user_activity(
                user_id=user_id,
                from_datetime=from_datetime,
                to_datetime=to_datetime,
            )

    async def get_user_activity_for_last_days(
        self,
        user_id: int,
        days: int,
    ) -> list[DailyActivityResponse]:
        if days < 0:
            raise ValueError("days must be greater than 0")

        today = utcnow().date()
        from_datetime = datetime.combine(
            date=today-timedelta(days=6),
            time=time.min,
            tzinfo=timezone.utc,
        )
        to_datetime = datetime.combine(
            date=today+timedelta(days=1),
            time=time.min,
            tzinfo=timezone.utc,
        )

        daily_activity = await self.get_user_activity(
            user_id=user_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

        return [
            DailyActivityResponse(
                date=current_date,
                value=daily_activity.get(current_date.date(), 0)
            )
            for current_date in (
                from_datetime + timedelta(days=offset)
                for offset in range(days)
            )
        ]

    async def get_user_progress(
        self,
        user_id: int,
    ) -> UserProgressResponse:
        async with self.uow_factory() as uow:
            return await uow.training_session_item_repo.get_user_progress(
                user_id=user_id,
            )

    # write
    async def start_training_session(
        self,
        user_id: int,
        deck_uuid: UUID,
        words_per_session: SessionSize,
        prompt_side: Literal["front", "back"],
    ) -> PracticeSessionResponse:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(
                deck_uuid=deck_uuid,
                load=DeckLoad(
                    user=True,
                ),
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
                deck_title_snapshot=deck.title,
                requested_count=words_per_session,
                answered_count=0,
                correct_count=0,
                wrong_count=0,
                prompt_side=prompt_side,
                answer_side=answer_side,
            )
            uow.training_session_repo.add(training_session)

            await uow.flush()

            positions = pick_random_positions(
                words_count=deck.words_count,
                count=words_per_session,
            )

            training_session_items = await uow.training_session_item_repo.create_snapshot(
                training_session_id=training_session.id,
                deck_id=deck.id,
                prompt_side=prompt_side,
                answer_side=answer_side,
                words_per_session=words_per_session,
                positions=positions,
            )

            if positions is not None and len(training_session_items) < words_per_session:
                gap_items = await uow.training_session_item_repo.fill_snapshot_gap(
                    training_session_id=training_session.id,
                    deck_id=deck.id,
                    prompt_side=prompt_side,
                    answer_side=answer_side,
                    needed_count=words_per_session - len(training_session_items),
                    sequence_offset=len(training_session_items),
                )
                training_session_items.extend(gap_items)

            if not training_session_items:
                raise DeckIsEmptyError()

            training_session.requested_count = len(training_session_items)

            response = PracticeSessionResponse(
                training_session_uuid=training_session.uuid,
                deck_uuid=deck.uuid,
                prompt_side=training_session.prompt_side,
                answer_side=training_session.answer_side,
                total_count=training_session.requested_count,
                answered_count=training_session.answered_count,
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

            await self.cache_service.invalidate_library_deck_pages(
                user_ids=[user_id],
            )

            return response

    async def record_activity(
        self,
        user_id: int,
        session_uuid: UUID,
        payload: TrainingSessionActivityRequest,
    ) -> TrainingSessionActivityResponse:
        async with self.uow_factory() as uow:
            training_session = await self._get_by_uuid(
                uow=uow,
                session_uuid=session_uuid,
                for_update=True,
            )

            if training_session.user_id != user_id:
                raise TrainingSessionNotFoundError()
            if training_session.status != TrainingSessionStatus.IN_PROGRESS:
                return TrainingSessionActivityResponse(
                    tracker_uuid=None,
                )

            event = payload.event
            now = utcnow()
            if now < training_session.started_at:
                raise RequestValueError("Activity must not precede started_at", failed_field="activity_last_seen_at")

            if event == "resume":
                training_session.activity_tracker_uuid = uuid.uuid7()
                training_session.activity_last_seen_at = now
            elif event == "heartbeat":
                if payload.tracker_uuid != training_session.activity_tracker_uuid:
                    return TrainingSessionActivityResponse(
                        tracker_uuid=None,
                    )
                self._accrue_activity(
                    training_session=training_session,
                    now=now,
                )
            elif event == "pause":
                if payload.tracker_uuid != training_session.activity_tracker_uuid:
                    return TrainingSessionActivityResponse(
                        tracker_uuid=None,
                    )
                self._accrue_activity(
                    training_session=training_session,
                    now=now,
                )
                training_session.activity_tracker_uuid = None
                training_session.activity_last_seen_at = None
            await uow.commit()

            return TrainingSessionActivityResponse(
                tracker_uuid=training_session.activity_tracker_uuid,
            )

    async def submit_answer(
            self,
            user_id: int,
            training_session_uuid: UUID,
            sequence_number: int,
            user_answer: UserAnswer,
    ) -> SubmitAnswerResponse:
        async with self.uow_factory() as uow:
            user_deck_changed = False
            training_session = await self._get_by_uuid(
                uow=uow,
                session_uuid=training_session_uuid,
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
                    answered_count=training_session.answered_count,
                    correct_count=training_session.correct_count,
                    total_count=training_session.requested_count,
                    is_finished=True if training_session.finished_at else False,
                    time_to_complete=(
                        training_session.active_study_time_ms // 1000
                        if training_session.finished_at is not None
                        else None
                    ),
                )
                return response

            if training_session.finished_at is not None:
                raise TrainingSessionAlreadyFinishedError()

            now = utcnow()
            if now < training_session.started_at:
                raise RequestValueError("Answer must not precede started_at", failed_field="answered_at")
            item.is_answered = True
            item.answered_at = now
            training_session.answered_count += 1

            self._accrue_activity(
                training_session=training_session,
                now=now,
            )
        
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
                item.user_typed_text = user_answer.answer.strip()

            # в статистику идут только завершенные сессии
            if (
                training_session.answered_count == training_session.requested_count 
                and 
                training_session.finished_at is None
            ):
                training_session.finished_at = now
                training_session.status = TrainingSessionStatus.COMPLETED
                training_session.activity_last_seen_at = None
                training_session.activity_tracker_uuid = None
                await self._update_user_deck_after_session(
                        uow=uow,
                        user_id=user_id,
                        training_session=training_session,
                    )
                user_deck_changed = training_session.deck_id is not None

            response = SubmitAnswerResponse(
                    is_correct=item.is_correct, 
                    answer_text=item.answer_text,
                    answered_count=training_session.answered_count,
                    correct_count=training_session.correct_count,
                    total_count=training_session.requested_count,
                    is_finished=True if training_session.finished_at else False,
                    time_to_complete=(
                        training_session.active_study_time_ms // 1000
                        if training_session.finished_at is not None
                        else None
                    ),
                )

            await uow.commit()

            if user_deck_changed:
                await self.cache_service.invalidate_user_decks(
                    identities=[(training_session.user_id, training_session.deck_id)],
                )
            
            return response
