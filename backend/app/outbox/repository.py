from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.utils import utcnow
from app.outbox.models import OutboxMessage


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, message: OutboxMessage) -> None:
        self.session.add(message)

    async def get_pending(
        self, *, event_types: Sequence[str], created_before: datetime, limit: int,
    ) -> list[OutboxMessage]:
        if not event_types:
            return []
        result = await self.session.scalars(
            select(OutboxMessage)
            .where(
                OutboxMessage.published.is_(False),
                OutboxMessage.event_type.in_(event_types),
                # Свежие события ещё доставляет запрос, который их создал.
                OutboxMessage.created_at < created_before,
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

    async def delete_published(self, *, cutoff: datetime, limit: int) -> int:
        batch = (
            select(OutboxMessage.id)
            .where(
                OutboxMessage.published.is_(True),
                OutboxMessage.published_at < cutoff,
            )
            .order_by(OutboxMessage.id)
            .limit(limit)
        )
        result = await self.session.execute(
            delete(OutboxMessage)
            .where(OutboxMessage.id.in_(batch))
            .returning(OutboxMessage.id)
            .execution_options(synchronize_session=False)
        )
        return len(result.all())
