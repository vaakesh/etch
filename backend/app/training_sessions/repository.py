from collections.abc import Sequence
from datetime import datetime, time, timedelta
from typing import Literal
from uuid import UUID

from app.cards.models import Card
from app.decks.models import Deck, DeckCard
from app.training_sessions.models import TrainingSession, TrainingSessionItem, TrainingSessionStatus
from sqlalchemy import Date, Integer, and_, case, cast, false, func, insert, literal, null, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.bff.schemas import UserProgressResponse
from app.common.utils import utcnow


class TrainingSessionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, training_session_item: TrainingSessionItem) -> None:
        self.session.add(training_session_item)

    async def get_user_progress(
        self,
        user_id: int,
    ) -> UserProgressResponse:
        timezone_name = "UTC"

        completed_items = (
            select(
                TrainingSessionItem.original_card_uuid,
                TrainingSessionItem.is_correct,
                TrainingSessionItem.answered_at,
            )
            .join(
                TrainingSession,
                TrainingSession.id == TrainingSessionItem.training_session_id,
            )
            .where(
                TrainingSession.user_id == user_id,
                TrainingSession.status == TrainingSessionStatus.COMPLETED,
                TrainingSessionItem.is_answered.is_(True),
            )
            .cte("completed_items")
        )

        week_cutoff = datetime.combine(
            utcnow().date() - timedelta(days=6),
            time.min
        )

        weekly_answered = func.count().filter(
            completed_items.c.answered_at >= week_cutoff,
        )

        weekly_correct = func.count().filter(
            completed_items.c.answered_at >= week_cutoff,
            completed_items.c.is_correct.is_(True),
        )

        item_stats = (
            select(
                func.count(
                    func.distinct(completed_items.c.original_card_uuid)
                ).label("user_words_explored"),
                weekly_answered.label("weekly_answered"),
                weekly_correct.label("weekly_correct"),
            )
            .cte("item_stats")
        )

        session_stats = (
            select(
                func.coalesce(
                    cast(
                        func.sum(
                            func.extract(
                                "epoch",
                                TrainingSession.finished_at
                                - TrainingSession.started_at,
                            )
                        ),
                        Integer,
                    ),
                    0,
                ).label("user_total_study_time")
            )
            .where(
                TrainingSession.user_id == user_id,
                TrainingSession.status == TrainingSessionStatus.COMPLETED,
                TrainingSession.finished_at.is_not(None),
            )
            .cte("session_stats")
        )

        activity_day = cast(
            func.timezone(
                timezone_name,
                completed_items.c.answered_at,
            ),
            Date,
        ).label("activity_day")

        activity_days = (
            select(activity_day)
            .distinct()
            .cte("activity_days")
        )

        numbered_days = (
            select(
                activity_days.c.activity_day,
                (
                    activity_days.c.activity_day
                    - cast(
                        func.row_number().over(
                            order_by=activity_days.c.activity_day
                        ),
                        Integer,
                    )
                ).label("island"),
            )
            .cte("numbered_days")
        )

        streaks = (
            select(
                func.max(
                    numbered_days.c.activity_day
                ).label("last_day"),
                func.count().label("streak"),
            )
            .group_by(numbered_days.c.island)
            .cte("streaks")
        )

        today = cast(
            func.timezone(timezone_name, func.now()),
            Date,
        )

        current_streak = func.coalesce(
            select(streaks.c.streak)
            .where(streaks.c.last_day >= today - 1)
            .order_by(streaks.c.last_day.desc())
            .limit(1)
            .scalar_subquery(),
            0,
        )

        stmt = (
            select(
                item_stats.c.user_words_explored,
                case(
                    (item_stats.c.weekly_answered == 0, 0),
                    else_=cast(
                        func.round(
                            item_stats.c.weekly_correct
                            * 100.0
                            / item_stats.c.weekly_answered
                        ),
                        Integer,
                    ),
                ).label("user_weekly_accuracy"),
                current_streak.label("user_current_streak"),
                session_stats.c.user_total_study_time,
            )
            .select_from(item_stats)
            .join(session_stats, true())
        )

        result = await self.session.execute(stmt)
        row = result.mappings().one()
        
        return UserProgressResponse.model_validate(row)


    async def get_user_daily_activity(
        self,
        user_id: int,
        from_date: datetime,
        to_date: datetime | None,
    ) -> list[tuple[int, datetime]]:
        stmt = (
            select(TrainingSessionItem.id, TrainingSessionItem.answered_at)
            .join(TrainingSession, TrainingSessionItem.training_session_id == TrainingSession.id)
            .where(
                and_(
                    TrainingSession.status == TrainingSessionStatus.COMPLETED,
                    TrainingSessionItem.is_answered.is_(True),
                    TrainingSession.user_id == user_id,
                    TrainingSession.started_at >= from_date,
                )
            )
        )
        if to_date is not None:
            stmt = stmt.where(TrainingSession.started_at < to_date)
        result = await self.session.execute(stmt)
        rows = result.tuples().all()
        return rows

    async def get_session_history(
        self,
        user_id: int,
        session_uuid: UUID,
        last_sequence_number: int,
        page_size: int = 30,
        only_answered_items: bool = False,
    ) -> Sequence[tuple[TrainingSessionItem, TrainingSessionStatus]]:
        # stmt = (
        #     select(TrainingSessionItem, TrainingSession.status)
        #     .join(
        #         TrainingSession,
        #         TrainingSession.id == TrainingSessionItem.training_session_id
        #     )
        #     .where(
        #         TrainingSession.uuid == session_uuid,
        #         TrainingSession.user_id == user_id,
        #         TrainingSessionItem.sequence_number > last_sequence_number,
        #     )
        # )
        # if only_answered_items:
        #     stmt = stmt.where(
        #         TrainingSessionItem.is_answered.is_(True),
        #     )
        # stmt = stmt.limit(page_size)
        # result = await self.session.execute(stmt)
        # rows = result.all()
        # return list(rows)
        conditions = [
            TrainingSessionItem.training_session_id == TrainingSession.id,
            TrainingSessionItem.sequence_number > last_sequence_number,
        ]
        if only_answered_items:
            conditions.append(TrainingSessionItem.is_answered.is_(True))

        stmt = (
            select(TrainingSessionItem, TrainingSession.status)
            .select_from(TrainingSession)
            .outerjoin(TrainingSessionItem, and_(*conditions))
            .where(
                TrainingSession.uuid == session_uuid,
                TrainingSession.user_id == user_id,
            )
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return rows

    async def get_item_by_sequence_number_and_session_id(
        self,
        training_session_id: int,
        sequence_number: int,
        for_update: bool = False,
    ) -> TrainingSessionItem | None:
        stmt = (
            select(TrainingSessionItem)
            .where(
                TrainingSessionItem.training_session_id == training_session_id,
                TrainingSessionItem.sequence_number == sequence_number,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_next_cards(
            self,
            training_session_id: int,
    ) -> list[TrainingSessionItem]:
        stmt = (
            select(TrainingSessionItem)
            .where(
                TrainingSessionItem.training_session_id == training_session_id,
                TrainingSessionItem.is_answered.is_(False),
            )
            .order_by(TrainingSessionItem.sequence_number)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_snapshot(
            self,
            training_session_id: int,
            deck_id: int,
            prompt_side: Literal["front", "back"],
            answer_side: Literal["front", "back"],
    ) -> list[TrainingSessionItem]:
        """
        создает снимок карточек в случайном порядке
        """

        side_columns = {
            "front": (Card.front_text, Card.front_lang),
            "back": (Card.back_text, Card.back_lang),
        }

        prompt_text_column, prompt_lang_column = side_columns[prompt_side]
        answer_text_column, answer_lang_column = side_columns[answer_side]

        sequence_number = (
            func.row_number().over(order_by=func.random())
        )

        snapshot_query = (
            select(
                literal(training_session_id),
                sequence_number,
                Card.uuid,
                prompt_text_column,
                answer_text_column,
                prompt_lang_column,
                answer_lang_column,
                false(),
                null(),
                null(),
            )
            .select_from(DeckCard)
            .join(Card, Card.id == DeckCard.card_id)
            .where(DeckCard.deck_id == deck_id)
        )
        
        stmt = (
            insert(TrainingSessionItem)
            .from_select(
                [
                    "training_session_id",
                    "sequence_number",
                    "original_card_uuid",
                    "prompt_text",
                    "answer_text",
                    "prompt_lang",
                    "answer_lang",
                    "is_answered",
                    "is_correct",
                    "answered_at",
                ],
                snapshot_query,
            )
            .returning(TrainingSessionItem)
        )

        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        items.sort(key=lambda item: item.sequence_number)

        return items


    


class TrainingSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_uuid(
            self, 
            session_uuid: UUID,
            for_update: bool = False,
        ) -> TrainingSession | None:
        stmt = (
            select(TrainingSession)
            .options(joinedload(TrainingSession.deck).load_only(Deck.uuid))
            .where(TrainingSession.uuid == session_uuid)
        )
        if for_update:
            stmt = stmt.with_for_update(of=TrainingSession)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_sessions_by_user_id(
        self,
        user_id: int,
        cursor_started_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 10,
    ) -> tuple[Sequence[TrainingSession], bool]:
        stmt = (
            select(TrainingSession)
            .options(joinedload(TrainingSession.deck).load_only(Deck.uuid))
            .where(
                TrainingSession.user_id == user_id,
            )
        )

        if cursor_started_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    TrainingSession.started_at < cursor_started_at,
                    and_(
                        TrainingSession.started_at == cursor_started_at,
                        TrainingSession.id < cursor_id,
                    )
                )
            )

        stmt = stmt.order_by(TrainingSession.started_at.desc(), TrainingSession.id.desc())
        stmt = stmt.limit(limit=limit + 1)

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def get_all_unfinished_sessions_by_user_id(
        self,
        user_id: int,
        cursor_started_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 10,
    ) -> tuple[Sequence[TrainingSession], bool]:
        stmt = (
            select(TrainingSession)
            .options(joinedload(TrainingSession.deck).load_only(Deck.uuid))
            .where(
                TrainingSession.user_id == user_id,
                TrainingSession.status == TrainingSessionStatus.IN_PROGRESS,
            )
        )

        if cursor_started_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    TrainingSession.started_at < cursor_started_at,
                    and_(
                        TrainingSession.started_at == cursor_started_at,
                        TrainingSession.id < cursor_id,
                    )
                )
            )

        stmt = stmt.order_by(TrainingSession.started_at.desc(), TrainingSession.id.desc())
        stmt = stmt.limit(limit=limit + 1)

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def get_all_finished_sessions_by_user_id(
        self,
        user_id: int,
        status: TrainingSessionStatus | None = None,
        cursor_finished_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 10,
    ) -> tuple[Sequence[TrainingSession], bool]:
        stmt = (
            select(TrainingSession)
            .options(joinedload(TrainingSession.deck).load_only(Deck.uuid))
            .where(
                TrainingSession.user_id == user_id,
                TrainingSession.status == status,
            )
        )

        if cursor_finished_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    TrainingSession.finished_at < cursor_finished_at,
                    and_(
                        TrainingSession.finished_at == cursor_finished_at,
                        TrainingSession.id < cursor_id,
                    )
                )
            )

        stmt = stmt.order_by(TrainingSession.finished_at.desc(), TrainingSession.id.desc())
        stmt = stmt.limit(limit=limit + 1)

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def add(self, training_session: TrainingSession) -> None:
        self.session.add(training_session)

    async def delete(self, training_session: TrainingSession) -> None:
        await self.session.delete(training_session)

    async def refresh(self, training_session: TrainingSession) -> None:
        await self.session.refresh(training_session)

    async def get(self, training_session_id: int) -> TrainingSession | None:
        return await self.session.get(TrainingSession, training_session_id)