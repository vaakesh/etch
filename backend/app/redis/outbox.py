from typing import Any

from app.redis.invalidation import CacheInvalidator, load_scopes

CACHE_INVALIDATION_EVENT_TYPE = "cache.invalidation.v1"


class CacheInvalidationHandler:
    """Deliver scopes; Redis errors leave the outbox event pending."""

    def __init__(self, invalidator: CacheInvalidator) -> None:
        self.invalidator = invalidator

    async def __call__(self, message_data: dict[str, Any]) -> None:
        await self.invalidator.invalidate(*load_scopes(message_data))
