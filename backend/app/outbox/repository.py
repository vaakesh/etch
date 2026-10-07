from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils import utcnow
from app.outbox.models import OutboxMessage


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, message: OutboxMessage) -> None:
        self.session.add(message)

    async def get_pending(
        self, *, event_types: Sequence[str], limit: int,
    ) -> list[OutboxMessage]:
        if not event_types:
            return []
        result = await self.session.scalars(
            select(OutboxMessage)
            .where(
                OutboxMessage.published.is_(False),
                OutboxMessage.event_type.in_(event_types),
            )
            .order_by(OutboxMessage.id)
            .limit(limit)
        )
        return list(result.all())

    async def mark_published(self, message_id: int) -> bool:
        result = await self.session.execute(
            update(OutboxMessage)
            .where(
                OutboxMessage.id == message_id,
                OutboxMessage.published.is_(False)
            )
            .values(published=True, published_at=utcnow())
            .returning(OutboxMessage.id)
            .execution_options(synchronize_session=False)
        )
        return result.scalar_one_or_none() is not None
