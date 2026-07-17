from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def get_all_by_card_id(
        self,
        card_id: int,
        limit: int = 100,
    ) -> list[DeckCard]:
        stmt = (
            select(DeckCard)
            .where(DeckCard.card_id == card_id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, deck_card: DeckCard) -> None:
        self.session.add(deck_card)

    async def delete(self, deck_card: DeckCard) -> None:
        await self.session.delete(deck_card)

    async def refresh(self, deck_card: DeckCard) -> None:
        await self.session.refresh(deck_card)