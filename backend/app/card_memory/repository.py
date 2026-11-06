from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.card_memory.models import CardMemoryState
from app.card_memory.replay import MemoryKey, ReviewEvent
from app.card_memory.utils import effective_rating
from app.cards.models import Card
from app.decks.models import Deck, DeckCard, UserDeck
from app.fsrs.types import CardState
from app.tracing import traced
from app.training_sessions.models import CardSide, TrainingSession, TrainingSessionItem
from sqlalchemy import ColumnElement, and_, func, literal, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

# Ключ памяти в журнале ответов: пользователь и слово из item, направление из сессии.
# user_id из item, чтобы история слова читалась по индексу только этого пользователя
JOURNAL_KEY_COLUMNS = (
    TrainingSessionItem.user_id,
    TrainingSessionItem.learning_key_snapshot,
    TrainingSession.prompt_side,
)
STATE_KEY_COLUMNS = (
    CardMemoryState.user_id,
    CardMemoryState.learning_key,
    CardMemoryState.prompt_side,
)


@dataclass(frozen=True, slots=True)
class DueSideSummary:
    due_now: int
    due_today: int
    next_due_at: datetime | None


@dataclass(frozen=True, slots=True)
class DueCard:
    card_id: int
    learning_key: UUID
    due: datetime


def _studiable_deck(user_id: int) -> ColumnElement[bool]:
    # Колода, которую пользователь сейчас может тренировать: своя активная или
    # публичная из библиотеки. Архивные исключены, в них submit_answer запрещён
    in_library = (
        select(UserDeck.deck_id)
        .where(UserDeck.user_id == user_id, UserDeck.deck_id == Deck.id)
        .exists()
    )
    return and_(
        Deck.state == "active",
        or_(Deck.user_id == user_id, and_(Deck.is_public.is_(True), in_library)),
    )


class CardMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @traced("card_memory.repository.get_due_summary")
    async def get_due_summary(
        self,
        user_id: int,
        now: datetime,
        end_of_day: datetime,
    ) -> dict[CardSide, DueSideSummary]:
        # Слово считается, если у пользователя есть доступная карточка с этим
        # learning_key. Память недоступных слов хранится, но не показывается
        has_studiable_card = (
            select(Card.id)
            .join(DeckCard, DeckCard.card_id == Card.id)
            .join(Deck, Deck.id == DeckCard.deck_id)
            .where(
                Card.learning_key == CardMemoryState.learning_key,
                _studiable_deck(user_id),
            )
            .exists()
        )
        due = CardMemoryState.due
        stmt = (
            select(
                CardMemoryState.prompt_side,
                func.count().filter(due <= now).label("due_now"),
                func.count().filter(due < end_of_day).label("due_today"),
                func.min(due).filter(due > now).label("next_due_at"),
            )
            .where(CardMemoryState.user_id == user_id, has_studiable_card)
            .group_by(CardMemoryState.prompt_side)
        )
        rows = (await self.session.execute(stmt)).all()
        summary = {
            side: DueSideSummary(due_now=0, due_today=0, next_due_at=None)
            for side in ("front", "back")
        }
        for row in rows:
            summary[row.prompt_side] = DueSideSummary(
                due_now=row.due_now,
                due_today=row.due_today,
                next_due_at=row.next_due_at,
            )
        return summary

    @traced("card_memory.repository.get_due_cards")
    async def get_due_cards(
        self,
        user_id: int,
        prompt_side: CardSide,
        until: datetime,
        limit: int,
    ) -> list[DueCard]:
        # Одна карточка на слово: сначала из своей колоды, затем с меньшим id
        due_words = (
            select(
                CardMemoryState.learning_key,
                CardMemoryState.due,
                Card.id.label("card_id"),
            )
            .distinct(CardMemoryState.learning_key)
            .join(Card, Card.learning_key == CardMemoryState.learning_key)
            .join(DeckCard, DeckCard.card_id == Card.id)
            .join(Deck, Deck.id == DeckCard.deck_id)
            .where(
                CardMemoryState.user_id == user_id,
                CardMemoryState.prompt_side == prompt_side,
                CardMemoryState.due < until,
                _studiable_deck(user_id),
            )
            .order_by(
                CardMemoryState.learning_key,
                (Deck.user_id == user_id).desc(),
                Card.id,
            )
            .subquery("due_words")
        )
        # Самые просроченные первыми
        stmt = (
            select(due_words)
            .order_by(due_words.c.due, due_words.c.card_id)
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            DueCard(card_id=row.card_id, learning_key=row.learning_key, due=row.due)
            for row in rows
        ]

    @traced("card_memory.repository.get_or_create_for_update")
    async def get_or_create_for_update(
        self,
        user_id: int,
        learning_key: UUID,
        prompt_side: CardSide,
        now: datetime,
    ) -> CardMemoryState:
        locked = (
            select(CardMemoryState)
            .where(
                CardMemoryState.user_id == user_id,
                CardMemoryState.learning_key == learning_key,
                CardMemoryState.prompt_side == prompt_side,
            )
            .with_for_update()
        )
        memory = (await self.session.execute(locked)).scalar_one_or_none()
        if memory is not None:
            return memory

        # Слово отвечают впервые. ON CONFLICT DO NOTHING ждёт параллельную вставку
        # той же строки, после этого SELECT FOR UPDATE её блокирует
        await self.session.execute(
            pg_insert(CardMemoryState)
            .values(
                user_id=user_id,
                learning_key=learning_key,
                prompt_side=prompt_side,
                state=CardState.LEARNING,
                step=0,
                due=now,
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "learning_key", "prompt_side"],
            )
        )
        return (await self.session.execute(locked)).scalar_one()

    @traced("card_memory.repository.get_states")
    async def get_states(
        self,
        keys: Sequence[MemoryKey],
        for_update: bool = False,
    ) -> dict[MemoryKey, CardMemoryState]:
        # Строки блокируются в порядке ключа, как их перебирает пересборка
        stmt = (
            select(CardMemoryState)
            .where(tuple_(*STATE_KEY_COLUMNS).in_(keys))
            .order_by(*STATE_KEY_COLUMNS)
        )
        if for_update:
            stmt = stmt.with_for_update()
        states = (await self.session.scalars(stmt)).all()
        return {
            (state.user_id, state.learning_key, state.prompt_side): state
            for state in states
        }

    @traced("card_memory.repository.create_missing")
    async def create_missing(
        self,
        keys: Sequence[MemoryKey],
        now: datetime,
    ) -> None:
        # Пустые строки под пересборку. Строку, которую успел создать
        # параллельный submit_answer, не трогаем
        await self.session.execute(
            pg_insert(CardMemoryState)
            .values([
                {
                    "user_id": user_id,
                    "learning_key": learning_key,
                    "prompt_side": prompt_side,
                    "state": CardState.LEARNING,
                    "step": 0,
                    "due": now,
                }
                for user_id, learning_key, prompt_side in sorted(keys)
            ])
            .on_conflict_do_nothing(
                index_elements=["user_id", "learning_key", "prompt_side"],
            )
        )

    @traced("card_memory.repository.get_journal_keys")
    async def get_journal_keys(
        self,
        after: MemoryKey | None,
        limit: int,
    ) -> list[MemoryKey]:
        # Страница ключей из журнала ответов, keyset-пагинация по ключу
        stmt = (
            select(*JOURNAL_KEY_COLUMNS)
            .distinct()
            .join(
                TrainingSession,
                TrainingSession.id == TrainingSessionItem.training_session_id,
            )
            .where(
                TrainingSessionItem.is_answered.is_(True),
                TrainingSessionItem.learning_key_snapshot.is_not(None),
            )
            .order_by(*JOURNAL_KEY_COLUMNS)
            .limit(limit)
        )
        if after is not None:
            after_values = (
                literal(value, type_=column.type)
                for value, column in zip(after, JOURNAL_KEY_COLUMNS, strict=True)
            )
            stmt = stmt.where(tuple_(*JOURNAL_KEY_COLUMNS) > tuple_(*after_values))
        rows = (await self.session.execute(stmt)).all()
        return [tuple(row) for row in rows]

    async def get_review_events(self, key: MemoryKey) -> list[ReviewEvent]:
        # История ответов одного слова в одном направлении, по порядку ответов
        return await self.get_review_events_for_keys([key])

    @traced("card_memory.repository.get_review_events_for_keys")
    async def get_review_events_for_keys(
        self,
        keys: Sequence[MemoryKey],
    ) -> list[ReviewEvent]:
        stmt = (
            select(
                *JOURNAL_KEY_COLUMNS,
                TrainingSessionItem.is_correct,
                TrainingSessionItem.self_rating,
                TrainingSessionItem.answered_at,
            )
            .join(
                TrainingSession,
                TrainingSession.id == TrainingSessionItem.training_session_id,
            )
            .where(
                TrainingSessionItem.is_answered.is_(True),
                tuple_(*JOURNAL_KEY_COLUMNS).in_(keys),
            )
            # Порядок нужен только внутри ключа: replay ведёт ключи независимо
            .order_by(TrainingSessionItem.answered_at, TrainingSessionItem.id)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            ReviewEvent(
                user_id=row.user_id,
                learning_key=row.learning_key_snapshot,
                prompt_side=row.prompt_side,
                rating=effective_rating(row.is_correct, row.self_rating),
                answered_at=row.answered_at,
            )
            for row in rows
        ]
