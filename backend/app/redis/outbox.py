from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.common.types import PositiveInt
from app.redis.service import RedisCacheService

EXPIRED_ARCHIVED_DECKS_CACHE_INVALIDATION_EVENT_TYPE = (
    "decks.expired_archives.cache_invalidation.v1"
)


class ExpiredArchivedDecksCacheInvalidationPayload(BaseModel):
    """Cache keys affected by deletion of a batch of expired archived decks."""

    model_config = ConfigDict(extra="forbid")

    deck_ids: list[PositiveInt] = Field(default_factory=list)
    deck_uuids: list[UUID] = Field(default_factory=list)
    card_ids: list[PositiveInt] = Field(default_factory=list)
    card_uuids: list[UUID] = Field(default_factory=list)
    user_deck_keys: list[tuple[PositiveInt, PositiveInt]] = Field(default_factory=list)


class ExpiredArchivedDecksCacheInvalidationHandler:
    """Invalidate cache entries collected during expired archive cleanup."""

    def __init__(self, cache_service: RedisCacheService) -> None:
        if not cache_service.raise_errors:
            raise ValueError(
                "Expired archived decks invalidation requires a cache service with raise_errors=True"
            )
        self.cache_service = cache_service

    async def __call__(self, data: dict[str, Any]) -> None:
        payload = ExpiredArchivedDecksCacheInvalidationPayload.model_validate(data)
        # DEL is idempotent; a partially delivered event can safely be replayed.
        await self.cache_service.invalidate_decks(deck_ids=payload.deck_ids)
        await self.cache_service.invalidate_deck_ids_by_uuids(deck_uuids=payload.deck_uuids)
        await self.cache_service.invalidate_deck_cards(deck_ids=payload.deck_ids)
        await self.cache_service.invalidate_user_decks(identities=payload.user_deck_keys)
        await self.cache_service.invalidate_cards(card_ids=payload.card_ids)
        await self.cache_service.invalidate_card_ids_by_uuids(card_uuids=payload.card_uuids)
