from typing import Literal
from uuid import UUID

from sqlalchemy import false, insert, literal, null, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.training_sessions.models import TrainingSession, TrainingSessionItem
from app.cards.models import Card
from app.decks.models import DeckCard


class TrainingSessionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, training_session_item: TrainingSessionItem) -> None:
        self.session.add(training_session_item)

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

    async def get_item_by_uuid(
            self,
            item_uuid: UUID,
            for_update: bool = False,
    ) -> TrainingSessionItem | None:
        stmt = (
            select(TrainingSessionItem)
            .where(
                TrainingSessionItem.uuid == item_uuid,
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
        создает снимок карточек в порядке колоды
        """

        side_columns = {
            "front": (Card.front_text, Card.source_lang),
            "back": (Card.back_text, Card.target_lang),
        }

        prompt_text_column, prompt_lang_column = side_columns[prompt_side]
        answer_text_column, answer_lang_column = side_columns[answer_side]

        snapshot_query = (
            select(
                literal(training_session_id),
                DeckCard.position,
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
            .order_by(DeckCard.position)
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
        stmt = select(TrainingSession).where(TrainingSession.uuid == session_uuid)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_limit(self, limit: int = 10) -> list[TrainingSession]:
        stmt = select(TrainingSession).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_all_by_user_id(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[TrainingSession]:
        stmt = (
            select(TrainingSession)
            .where(TrainingSession.user_id == user_id)
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