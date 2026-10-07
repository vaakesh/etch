from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from app.outbox.models import OutboxMessage
from app.service import UnitOfWork

type OutboxHandler = Callable[[dict[str, Any]], Awaitable[None]]


class OutboxPublisher:
    """Deliver only registered event types. Handlers must tolerate redelivery.

    Network operations run without an open database transaction. Concurrent
    publishers may deliver the same message; delivery is at least once.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        handlers: Mapping[str, OutboxHandler],
    ) -> None:
        self.uow_factory = uow_factory
        self.handlers = dict(handlers)

    async def publish(self, message: OutboxMessage) -> bool:
        if message.published:
            return False

        handler = self.handlers[message.event_type]
        await handler(message.payload)

        async with self.uow_factory() as uow:
            published = await uow.outbox_repo.mark_published(message.id)
            await uow.commit()
        return published

    async def publish_pending(self, *, limit: int) -> int:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        async with self.uow_factory() as uow:
            messages = await uow.outbox_repo.get_pending(
                event_types=list(self.handlers), limit=limit,
            )
        published = 0
        for message in messages:
            published += await self.publish(message)
        return published
