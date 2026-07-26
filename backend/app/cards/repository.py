from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cards.models import Card
from app.bff.schemas import CardsLibraryPage


class CardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_cards_library_page(
            self,
            user_id: int,
            user_uuid: UUID,
            cursor: tuple[datetime, int] | None = None,
            limit: int = 50,
    ) -> tuple[list[CardsLibraryPage], bool]:
        stmt = (
            select(Card)
            .where(Card.user_id == user_id)
        )

        if cursor is not None:
            cursor_updated_at, cursor_id = cursor
            stmt = stmt.where(
                or_(
                    and_(
                        Card.updated_at == cursor_updated_at,
                        Card.id < cursor_id,
                    ),
                    Card.updated_at < cursor_updated_at,
                )
            )
        
        stmt = stmt.order_by(
            Card.updated_at.desc(),
            Card.id.desc(),
        ).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit

        cards = [CardsLibraryPage(
            card_uuid=card.uuid,
            card_owner_uuid=user_uuid,
            card_front_text=card.front_text,
            card_back_text=card.back_text,
            card_source_lang=card.source_lang,
            card_target_lang=card.target_lang,
            card_updated_at=card.updated_at,
        ) for card in rows[:limit]]

        return cards, has_more


    async def get_by_uuid(self, card_uuid: UUID) -> Card | None:
        stmt = select(Card).where(Card.uuid == card_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_limit(self, limit: int = 10) -> list[Card]:
        stmt = select(Card).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_by_user_id(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[Card]:
        stmt = (
            select(Card)
            .where(Card.user_id == user_id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, card: Card) -> None:
        self.session.add(card)

    async def delete(self, card: Card) -> None:
        await self.session.delete(card)

    async def refresh(self, card: Card) -> None:
        await self.session.refresh(card)