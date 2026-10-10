from typing import Any

from app.outbox.models import OutboxMessage
from app.redis.invalidation import CacheInvalidator, Scope, dump_scopes, load_scopes

CACHE_INVALIDATION_EVENT_TYPE = "cache.invalidation.v1"


def cache_invalidation_message(*items: Scope) -> OutboxMessage:
    return OutboxMessage(
        event_type=CACHE_INVALIDATION_EVENT_TYPE,
        payload=dump_scopes(*items),
    )


class CacheInvalidationHandler:
    """Deliver scopes; Redis errors leave the outbox event pending."""

    def __init__(self, invalidator: CacheInvalidator) -> None:
        self.invalidator = invalidator

    async def __call__(self, message_data: dict[str, Any]) -> None:
        await self.invalidator.invalidate(*load_scopes(message_data))
