from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from app.bff.schemas import DailyActivityResponse, UserProgressResponse
from app.cards.models import Card
from app.common.query import apply_date_pagination
from app.common.types import PositiveInt
from app.common.utils import utcnow
from app.decks.models import Deck, DeckCard
from app.training_sessions.models import (
    TrainingSession,
    TrainingSessionItem,
    TrainingSessionStatus,
)
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    and_,
    case,
    cast,
    exists,
    false,
    func,
    insert,
    literal,
    null,
    or_,
    select,
    true,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


class TrainingSessionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # helpers
    def _ranked_cards_subquery(
            self,
            training_session_id: PositiveInt,
            deck_id: PositiveInt,
            prompt_side: Literal["front", "back"],
            answer_side: Literal["front", "back"],
            sequence_number,
            where_extra: list,
    ):
        side_columns = {
            "front": (Card.front_text, Card.front_lang),
            "back": (Card.back_text, Card.back_lang),
        }

        prompt_text_column, prompt_lang_column = side_columns[prompt_side]
        answer_text_column, answer_lang_column = side_columns[answer_side]

        return (
            select(
                literal(training_session_id).label("training_session_id"),
                sequence_number.label("sequence_number"),
                Card.uuid.label("original_card_uuid"),
                prompt_text_column.label("prompt_text"),
                answer_text_column.label("answer_text"),
                prompt_lang_column.label("prompt_lang"),
                answer_lang_column.label("answer_lang"),
                false().label("is_answered"),
                cast(null(), Boolean).label("is_correct"),
                cast(null(), DateTime(timezone=True)).label("answered_at"),
            )
            .select_from(DeckCard)
            .join(Card, Card.id == DeckCard.card_id)
            .where(DeckCard.deck_id == deck_id, *where_extra)
            .subquery("ranked_cards")
        )

    async def _insert_snapshot_rows(
            self,
            ranked_cards,
            limit: int,
    ) -> list[TrainingSessionItem]:
        snapshot_query = (
            select(ranked_cards)
            .order_by(ranked_cards.c.sequence_number)
            .limit(limit)
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

    # base
    def add(self, training_session_item: TrainingSessionItem) -> None:
        self.session.add(training_session_item)

    # read
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
            .order_by(TrainingSessionItem.sequence_number.asc())
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return rows

    async def get_user_activity(
        self,
        user_id: int,
        from_datetime: datetime,
        to_datetime: datetime | None,
    ) -> dict[date, int]:
        activity_date = cast(TrainingSessionItem.answered_at, Date)

        stmt = (
            select(
                activity_date.label("date"),
                func.count(TrainingSessionItem.id).label("count"),
            )
            .join(
                TrainingSession,
                TrainingSessionItem.training_session_id == TrainingSession.id,
            )
            .where(
                TrainingSessionItem.is_answered.is_(True),
                TrainingSession.user_id == user_id,
                TrainingSessionItem.answered_at >= from_datetime,
            )
            .group_by(activity_date)
            .order_by(activity_date)
        )
        if to_datetime is not None:
            stmt = stmt.where(TrainingSessionItem.answered_at < to_datetime)
        result = await self.session.execute(stmt)
        rows = result.tuples().all()
        return dict(rows)

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
                        func.floor(
                            func.sum(TrainingSession.active_study_time_ms) / 1000
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

    # write
    async def create_snapshot(
            self,
            training_session_id: PositiveInt,
            deck_id: PositiveInt,
            prompt_side: Literal["front", "back"],
            answer_side: Literal["front", "back"],
            words_per_session: PositiveInt,
            positions: list[int] | None = None,
    ) -> list[TrainingSessionItem]:
        """
        создает снимок карточек в случайном порядке\n
        positions - заранее выбранные позиции карточек
        сужает выборку до этих позиций вместо
        сортировки всей колоды\n
        None - берём всю колоду
        """
        where_extra = (
            [DeckCard.position.in_(positions)]
            if positions is not None
            else []
        )

        ranked_cards = self._ranked_cards_subquery(
            training_session_id=training_session_id,
            deck_id=deck_id,
            prompt_side=prompt_side,
            answer_side=answer_side,
            sequence_number=func.row_number().over(order_by=func.random()),
            where_extra=where_extra,
        )

        return await self._insert_snapshot_rows(
            ranked_cards=ranked_cards,
            limit=words_per_session,
        )

    async def fill_snapshot_gap(
            self,
            training_session_id: PositiveInt,
            deck_id: PositiveInt,
            prompt_side: Literal["front", "back"],
            answer_side: Literal["front", "back"],
            needed_count: PositiveInt,
            sequence_offset: int,
    ) -> list[TrainingSessionItem]:
        """
        Добор карточек поверх уже вставленных create_snapshot - на случай,
        если выборка по позициям не набрала нужное количество (позиции,
        выбранные в python, не совпали с фактическими строками deck_cards).
        Исключает уже вставленные карточки и продолжает нумерацию с
        sequence_offset.
        """
        already_inserted = select(TrainingSessionItem.original_card_uuid).where(
            TrainingSessionItem.training_session_id == training_session_id,
        )

        ranked_cards = self._ranked_cards_subquery(
            training_session_id=training_session_id,
            deck_id=deck_id,
            prompt_side=prompt_side,
            answer_side=answer_side,
            sequence_number=(
                func.row_number().over(order_by=func.random())
                + sequence_offset
            ),
            where_extra=[Card.uuid.not_in(already_inserted)],
        )

        return await self._insert_snapshot_rows(
            ranked_cards=ranked_cards,
            limit=needed_count,
        )


    


class TrainingSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # base
    async def get(self, training_session_id: int) -> TrainingSession | None:
        return await self.session.get(TrainingSession, training_session_id)

    def add(self, training_session: TrainingSession) -> None:
        self.session.add(training_session)

    async def refresh(self, training_session: TrainingSession) -> None:
        await self.session.refresh(training_session)

    async def delete(self, training_session: TrainingSession) -> None:
        await self.session.delete(training_session)

    # read
    async def has_by_deck_id(
        self,
        deck_id: int,
        exclude_user_id: int | None,
    ) -> bool:
        query = exists().where(TrainingSession.deck_id == deck_id)
        if exclude_user_id is not None:
            query = query.where(TrainingSession.user_id != exclude_user_id)
        return bool(await self.session.scalar(select(query)))

    async def reassign_deck(
        self,
        from_deck_id: int,
        to_deck_id: int,
        exclude_user_id: int | None,
    ) -> list[int]:
        stmt = (
            update(TrainingSession)
            .where(TrainingSession.deck_id == from_deck_id)
            .values(deck_id=to_deck_id)
            .returning(TrainingSession.user_id)
        )
        if exclude_user_id is not None:
            stmt = stmt.where(TrainingSession.user_id != exclude_user_id)
        result = await self.session.execute(stmt)
        return sorted(set(result.scalars().all()))

    async def get_by_uuid(
            self, 
            session_uuid: UUID,
            for_update: bool = False,
        ) -> TrainingSession | None:
        stmt = (
            select(TrainingSession)
            .options(
                joinedload(TrainingSession.deck).load_only(
                    Deck.uuid,
                    Deck.title,
                )
            )
            .where(TrainingSession.uuid == session_uuid)
        )
        if for_update:
            stmt = stmt.with_for_update(of=TrainingSession)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_sessions_by_user_id(
        self,
        user_id: int,
        status: TrainingSessionStatus | None = None,
        cursor_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 10,
        order_by: Literal["started_at", "finished_at"] = "started_at",
    ) -> tuple[Sequence[TrainingSession], bool]:
        order_column = (
            TrainingSession.started_at
            if order_by == "started_at"
            else TrainingSession.finished_at
        )

        stmt = (
            select(TrainingSession)
            .options(
                joinedload(TrainingSession.deck).load_only(
                    Deck.uuid,
                    Deck.title,
                )
            )
            .where(
                TrainingSession.user_id == user_id,
            )
        )
        if status is not None:
            stmt = stmt.where(TrainingSession.status == status)

        stmt = apply_date_pagination(
            stmt,
            date_column=order_column,
            id_column=TrainingSession.id,
            cursor_at=cursor_at,
            cursor_id=cursor_id,
            limit=limit,
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more
