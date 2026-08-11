from datetime import datetime
from uuid import UUID

from app.cards.models import Card
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class CardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_uuids(
        self,
        card_uuids: list[UUID],
    ) -> list[Card]:
        stmt = (
            select(Card)
            .where(
                Card.uuid.in_(card_uuids),
            )
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return rows

    async def get_by_uuid(
            self, 
            card_uuid: UUID,
            for_update: bool = False,
        ) -> Card | None:
        stmt = select(Card).where(Card.uuid == card_uuid)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_user_id(
        self,
        user_id: int,
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

        if cursor_updated_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    Card.updated_at < cursor_updated_at,
                    and_(
                        Card.updated_at == cursor_updated_at,
                        Card.id < cursor_id,
                    )
                )
            )

        stmt = stmt.order_by(Card.updated_at.desc(), Card.id.desc())
        stmt = stmt.limit(limit + 1)

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    def add(self, card: Card) -> None:
        self.session.add(card)

    async def delete(self, card: Card) -> None:
        await self.session.delete(card)

    async def refresh(self, card: Card) -> None:
        await self.session.refresh(card)

    async def get(self, card_id: int) -> Card:
        return await self.session.get(Card, card_id)