from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cards.models import Card


class CardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
        user_id: UUID,
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