import logging
from datetime import datetime
from uuid import UUID

from app.cards.models import Card
from app.cards.schemas import InternalCard
from app.common.query import apply_date_pagination, apply_search
from app.common.types import SearchQuery
from app.decks.models import Deck, DeckCard
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class CardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # base
    async def get(self, card_id: int) -> Card:
        return await self.session.get(Card, card_id)

    def add(self, card: Card) -> None:
        self.session.add(card)

    def add_all(self, cards: list[Card]) -> None:
        self.session.add_all(cards)

    async def refresh(self, card: Card) -> None:
        await self.session.refresh(card)

    async def delete(self, card: Card) -> None:
        await self.session.delete(card)

    # read
    async def get_by_uuid(
            self, 
            card_uuid: UUID,
            for_update: bool = False,
        ) -> Card | None:
        stmt = select(Card).where(Card.uuid == card_uuid)
        if for_update:
            stmt = stmt.with_for_update(of=Card).execution_options(
                populate_existing=True,
            )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_card_in_deck(
        self,
        deck_uuid: UUID,
        card_uuid: UUID,
        viewer_id: int | None,
        for_update: bool = False,
    ) -> Card | None:
        access_condition = Deck.is_public.is_(True)

        if viewer_id is not None:
            access_condition = or_(
                access_condition,
                Deck.user_id == viewer_id,
            )

        stmt = (
            select(Card)
            .join(DeckCard, DeckCard.card_id == Card.id)
            .join(Deck, DeckCard.deck_id == Deck.id)
            .where(
                Card.uuid == card_uuid,
                Deck.uuid == deck_uuid,
                access_condition,
            )
        )
        if for_update:
            stmt = stmt.with_for_update(of=Card)

        result = await self.session.execute(stmt)
        rows = result.scalar_one_or_none()
        return rows

    async def get_by_ids(
        self,
        card_ids: list[int],
    ) -> list[Card]:
        stmt = (
            select(Card)
            .where(
                Card.id.in_(card_ids),
            )
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return rows

    async def get_all_by_user_id(
        self,
        user_id: int,
        search_query: SearchQuery = None,
        cursor_updated_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 50,
    ) -> tuple[list[Card], bool]:
        stmt = (
            select(Card)
            .where(
                Card.user_id == user_id,
            )
        )

        if search_query:
            logger.info(f"has search_query = '{search_query}'")
        stmt = apply_search(stmt, search_query, Card.front_text, Card.back_text)

        stmt = apply_date_pagination(
            stmt,
            date_column=Card.updated_at,
            id_column=Card.id,
            cursor_at=cursor_updated_at,
            cursor_id=cursor_id,
            limit=limit,
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more
