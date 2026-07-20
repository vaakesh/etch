from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cards.models import Card

from .models import Deck, DeckCard, UserDeck


class DeckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_uuid(self, deck_uuid: UUID) -> Deck | None:
        stmt = select(Deck).where(Deck.uuid == deck_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_limit(self, limit: int = 10) -> list[Deck]:
        stmt = select(Deck).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_by_user_id(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[Deck]:
        stmt = (
            select(Deck)
            .where(Deck.user_id == user_id)
            .limit(limit)
            .order_by(Deck.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_page_by_user_id(
        self,
        user_id: int,
        limit: int = 16,
        cursor: tuple[datetime, int] | None = None,
    ) -> tuple[list[Deck], bool]:
        stmt = select(Deck).where(Deck.user_id == user_id)

        if cursor is not None:
            cursor_updated_at, cursor_id = cursor
            stmt = stmt.where(
                or_(
                    Deck.updated_at < cursor_updated_at,
                    and_(
                        Deck.updated_at == cursor_updated_at,
                        Deck.id < cursor_id,
                    ),
                )
            )

        stmt = stmt.order_by(Deck.updated_at.desc(), Deck.id.desc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        decks = list(result.scalars().all())
        has_more = len(decks) > limit
        return decks[:limit], has_more
    
    async def get_user_statistics_by_decks(
            self,
            deck_ids: list[int],
            user_id: int,
    ) -> list[UserDeck]:
        if not deck_ids:
            return []
        
        stmt = (
            select(UserDeck)
            .where(
                UserDeck.user_id == user_id,
                UserDeck.deck_id.in_(deck_ids),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_public_by_limit(self, limit: int = 10) -> list[Deck]:
        stmt = (
            select(Deck)
            .where(Deck.is_public.is_(True))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, deck: Deck) -> None:
        self.session.add(deck)

    async def delete(self, deck: Deck) -> None:
        await self.session.delete(deck)

    async def refresh(self, deck: Deck) -> None:
        await self.session.refresh(deck)


class DeckCardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_uuid(self, deck_card_uuid: UUID) -> DeckCard | None:
        stmt = select(DeckCard).where(DeckCard.uuid == deck_card_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_deck_id_and_card_id(
        self,
        deck_id: int,
        card_id: int,
    ) -> DeckCard | None:
        stmt = (
            select(DeckCard)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.card_id == card_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_deck_id(
        self,
        deck_id: int,
        limit: int = 100,
    ) -> list[DeckCard]:
        stmt = (
            select(DeckCard)
            .where(DeckCard.deck_id == deck_id)
            .order_by(DeckCard.position.asc(), DeckCard.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_all_by_deck_ids(
        self,
        deck_ids: list[int],
        limit: int = 100,
    ) -> list[tuple[int, Card]]:
        if not deck_ids or limit <= 0:
            return []
        
        ranked_deck_cards = (
            select(
                DeckCard.deck_id.label("deck_id"),
                DeckCard.card_id.label("card_id"),
                DeckCard.position.label("position"),
                DeckCard.id.label("deck_card_id"),
                func.row_number()
                .over(
                    partition_by=DeckCard.deck_id,
                    order_by=(
                        DeckCard.position.asc(),
                        DeckCard.id.asc(),
                    ),
                )
                .label("row_number"),
            )
            .where(DeckCard.deck_id.in_(deck_ids))
            .subquery()
        )

        stmt = (
            select(ranked_deck_cards.c.deck_id, Card)
            .join(Card, Card.id == ranked_deck_cards.c.card_id)
            .where(ranked_deck_cards.c.row_number <= limit)
            .order_by(
                ranked_deck_cards.c.deck_id.asc(),
                ranked_deck_cards.c.position.asc(),
                ranked_deck_cards.c.deck_card_id.asc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    def add(self, deck_card: DeckCard) -> None:
        self.session.add(deck_card)

    async def delete(self, deck_card: DeckCard) -> None:
        await self.session.delete(deck_card)

    async def refresh(self, deck_card: DeckCard) -> None:
        await self.session.refresh(deck_card)
