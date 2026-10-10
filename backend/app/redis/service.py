from dataclasses import dataclass, field
import logging
import random
from collections.abc import Callable, Hashable
from typing import Literal, Protocol
from uuid import UUID

import orjson
from app.cards.schemas import InternalCard
from app.common.schemas import CursorPage
from app.common.types import NormalizedSearch
from app.decks.models import UserDeck
from app.decks.schemas import InternalDeck, InternalUserDeck
from app.errors import RequestValueError
from app.redis.errors import RateLimitError
from app.tracing import traced, trace_span
from app.redis.keys import (
    make_card_cache_key,
    make_card_uuid_cache_key,
    make_deck_cache_key,
    make_deck_cards_cache_key,
    make_deck_uuid_cache_key,
    make_library_cards_page_cache_key,
    make_library_cards_page_generation_cache_key,
    make_library_deck_page_cache_key,
    make_library_deck_page_generation_cache_key,
    make_user_cache_key,
    make_user_deck_cache_key,
    make_user_settings_cache_key,
    make_user_uuid_cache_key,
)
from app.redis.schemas import CacheLookupResult, LibraryPageCacheLookup, UserDeckIdentity
from app.redis.ttl import (
    CARD_ID_BY_UUID_TTL,
    CARD_TTL,
    DECK_CARDS_TTL,
    DECK_ID_BY_UUID_TTL,
    DECK_TTL,
    LIBRARY_PAGE_TTL,
    USER_DECK_TTL,
    USER_ID_BY_UUID,
    USER_SETTINGS_TTL,
    USER_TTL,
)
from redis.asyncio import Redis

from app.users.schemas import InternalUser, InternalUserSettings, UserProfileResponse
from app.decks.repository import DeckCardRepository, DeckRepository, UserDeckRepository
from app.cards.repository import CardRepository
from app.decks.utils import make_user_deck_identity

logger = logging.getLogger(__name__)

type RateLimitIdentity = Literal["user", "ip"]


class _UUIDCacheEntity(Protocol):
    uuid: UUID


@dataclass(frozen=True)
class RateLimitPolicy:
    route: str
    requests: int
    window_seconds: int


class RateLimit:
    def __init__(
        self,
        policy: RateLimitPolicy,
        rate_limiter: RedisRateLimiter,
        by_identity: RateLimitIdentity,
        identity_key: str,
    ):
        self.policy = policy
        self.rate_limiter = rate_limiter
        self.by_identity = by_identity
        self.identity_key = identity_key

    async def __call__(self):
        redis_key = (
            f"rate_limit:"
            f"{self.by_identity}:"
            f"{self.identity_key}:"
            f"{self.policy.route}"
        )

        can = await self.rate_limiter.check(
            redis_key=redis_key,
            requests=self.policy.requests,
            window_seconds=self.policy.window_seconds,
        )
        if not can:
            raise RateLimitError()

RATE_LIMIT_SCRIPT = """
    local value = redis.call('INCR', KEYS[1])

    if value == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[1])
    end

    return value
"""

class RedisRateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    @traced("redis.rate_limiter.check")
    async def check(
        self,
        redis_key: str,
        requests: int,
        window_seconds: int,
    ) -> bool:
        with trace_span("redis.rate_limiter.eval"):
            value = await self.redis.eval(
                RATE_LIMIT_SCRIPT,
                1,
                redis_key,
                window_seconds,
            )

        return value <= requests

class RedisCacheService:
    """
    Redis is a required dependency: Redis errors propagate to the caller.
    Invalid cache entries are treated as misses and removed when possible.
    """
    def __init__(self, redis: Redis):
        self.redis = redis

    # helpers

    @staticmethod
    def with_jitter(
            base: int, 
            spread: int = 300
        ) -> int:
        return base + random.randint(0, spread)

    async def _redis_set(
        self,
        *,
        key: str,
        value: bytes | str,
        ex: int,
    ) -> None:
        await self.redis.set(
            name=key,
            value=value,
            ex=self.with_jitter(base=ex),
        )

    async def _redis_get(
        self,
        key: str,
    ) -> str | None:
        return await self.redis.get(key)

    async def _redis_set_many(
        self,
        entries: dict[str, bytes | str],
        ex: int,
    ) -> None:
        if not entries:
            return

        pipe = self.redis.pipeline(transaction=False)

        for key, value in entries.items():
            pipe.set(
                name=key,
                value=value,
                ex=self.with_jitter(base=ex),
            )

        await pipe.execute()

    async def _redis_mget(
        self,
        keys: list[str],
    ) -> list[str | None]:
        if not keys:
            return []

        return await self.redis.mget(keys=keys)

    async def _redis_delete(
        self,
        key: str,
    ) -> None:
        await self.redis.delete(key)

    async def _redis_delete_many(
        self,
        keys: list[str],
    ) -> None:
        if not keys:
            return

        await self.redis.delete(*keys)

    async def _get_page_generation(
        self,
        user_id: int,
        key_generation_factory: Callable[[int], str],
    ) -> int | None:
        """
        returns valid generation starting from 0
        or returns None if the stored generation is invalid
        """
        key = key_generation_factory(user_id)

        generation = await self.redis.get(key)

        if generation is None:
            return 0

        try:
            parsed_generation = int(generation)
            if parsed_generation < 0:
                raise ValueError("Library cache generation must be non-negative")
            return parsed_generation
        except (TypeError, ValueError):
            logger.warning(
                "Ignoring invalid library cache generation",
                extra={
                    "cache_key": key,
                },
                exc_info=True,
            )
            return

    async def _get_library_cards_page_generation(
        self,
        user_id: int,
    ) -> int | None:
        """
        returns valid generation starting from 0
        or returns None if the stored generation is invalid
        """
        return await self._get_page_generation(
            user_id=user_id,
            key_generation_factory=make_library_cards_page_generation_cache_key,
        )

    async def _get_library_deck_page_generation(
        self,
        user_id: int,
    ) -> int | None:
        """
        returns valid generation starting from 0
        or returns None if the stored generation is invalid
        """
        return await self._get_page_generation(
            user_id=user_id,
            key_generation_factory=make_library_deck_page_generation_cache_key,
        )

    def _deserialize_cached_value[T](
        self,
        key: str,
        value: bytes | str,
        deserializer: Callable[[bytes | str], T],
    ) -> T | None:
        """
        returns deserialized value or None if error has occured
        """
        try:
            return deserializer(value)
        except (TypeError, ValueError, RequestValueError):
            logger.warning(
                "Ignoring invalid cached value",
                extra={
                    "cache_key": key,
                },
                exc_info=True,
            )
            return

    @staticmethod
    def _deserialize_id_list(
        value: bytes | str,
    ) -> list[int]:
        payload = orjson.loads(value)

        if not isinstance(payload, list):
            raise ValueError("Expected a list of IDs")

        ids: list[int] = []

        for index, item in enumerate(payload):
            if not isinstance(item, int) or isinstance(item, bool):
                raise ValueError(
                    f"Expected integer ID at index {index}"
                )

            ids.append(item)

        return ids


    # cache operations

    async def _cache_ids_by_uuids(
        self,
        entity_uuids: list[UUID],
        entity_ids: list[int],
        key_factory: Callable[[UUID], str],
        ttl: int,
    ) -> None:
        entries = {
            key_factory(entity_uuid): str(entity_id)
            for entity_uuid, entity_id
            in zip(entity_uuids, entity_ids, strict=True)
        }
        await self._redis_set_many(
            entries=entries,
            ex=ttl,
        )

    async def _get_cached_entities_by_uuids[T: _UUIDCacheEntity](
        self,
        entity_uuids: list[UUID],
        uuid_key_factory: Callable[[UUID], str],
        entity_key_factory: Callable[[int], str],
        entity_deserializer: Callable[[bytes | str], T],
    ) -> CacheLookupResult[UUID, T]:
        id_lookup = await self._get_many(
            identities=entity_uuids,
            key_factory=uuid_key_factory,
            deserializer=int,
        )

        entity_ids = list(dict.fromkeys(id_lookup.cached.values()))
        entity_lookup = await self._get_many(
            identities=entity_ids,
            key_factory=entity_key_factory,
            deserializer=entity_deserializer,
        )

        cached: dict[UUID, T] = {}
        missing: list[UUID] = []

        for entity_uuid in entity_uuids:
            entity_id = id_lookup.cached.get(entity_uuid)
            if entity_id is None:
                missing.append(entity_uuid)
                continue

            entity = entity_lookup.cached.get(entity_id)
            if entity is None or entity.uuid != entity_uuid:
                missing.append(entity_uuid)
                continue

            cached[entity_uuid] = entity

        return CacheLookupResult(
            cached=cached,
            missing=missing,
        )

    @traced("redis.cache.cache_users")
    async def cache_users(
        self,
        users: list[InternalUser],
    ) -> None:
        if not users:
            return

        entries = {
            make_user_cache_key(
                user.id
            ): user.model_dump_json()
            for user in users
        }
        await self._redis_set_many(
            entries=entries,
            ex=USER_TTL,
        )

        await self._cache_ids_by_uuids(
            entity_uuids=[user.uuid for user in users],
            entity_ids=[user.id for user in users],
            key_factory=make_user_uuid_cache_key,
            ttl=USER_ID_BY_UUID,
        )

    async def get_cached_users(
        self,
        user_ids: list[int],
    ) -> CacheLookupResult[int, InternalUser]:
        return await self._get_many(
            identities=user_ids,
            key_factory=make_user_cache_key,
            deserializer=InternalUser.model_validate_json,
        )

    @traced("redis.cache.get_cached_users_by_uuids")
    async def get_cached_users_by_uuids(
        self,
        user_uuids: list[UUID],
    ) -> CacheLookupResult[UUID, InternalUser]:
        return await self._get_cached_entities_by_uuids(
            entity_uuids=user_uuids,
            uuid_key_factory=make_user_uuid_cache_key,
            entity_key_factory=make_user_cache_key,
            entity_deserializer=InternalUser.model_validate_json,
        )

    @traced("redis.cache.cache_users_settings")
    async def cache_users_settings(
        self,
        users_settings: list[InternalUserSettings],
    ) -> None:
        entries = {
            make_user_settings_cache_key(
                user_id=user_settings.user_id,
            ): user_settings.model_dump_json()
            for user_settings in users_settings
        }
        await self._redis_set_many(
            entries=entries,
            ex=USER_SETTINGS_TTL,
        )

    @traced("redis.cache.get_cached_users_settings")
    async def get_cached_users_settings(
        self,
        user_ids: list[int],
    ) -> CacheLookupResult[int, InternalUserSettings]:
        return await self._get_many(
            identities=user_ids,
            key_factory=make_user_settings_cache_key,
            deserializer=InternalUserSettings.model_validate_json,
        )

    @traced("redis.cache.cache_user_decks")
    async def cache_user_decks(
        self,
        user_id: int,
        user_decks: list[UserDeck],
    ) -> None:
        entries = {
            make_user_deck_cache_key(
                identity=make_user_deck_identity(
                    user_id=user_deck.user_id, deck_id=user_deck.deck_id,
                ),
            ): InternalUserDeck.model_validate(user_deck).model_dump_json()
            for user_deck in user_decks
        }

        await self._redis_set_many(
            entries=entries,
            ex=USER_DECK_TTL,
        )

    @traced("redis.cache.get_cached_user_decks")
    async def get_cached_user_decks(
        self,
        user_id: int,
        deck_ids: list[int],
    ) -> CacheLookupResult[UserDeckIdentity, InternalUserDeck]:
        identities: list[UserDeckIdentity] = [
            make_user_deck_identity(user_id=user_id, deck_id=deck_id)
            for deck_id in deck_ids
        ]
        result = await self._get_many(
            identities=identities,
            key_factory=make_user_deck_cache_key,
            deserializer=InternalUserDeck.model_validate_json
        )
        return result

    @traced("redis.cache.cache_library_cards_page")
    async def cache_library_cards_page(
        self,
        user_id: int,
        card_ids: list[int],
        expected_generation: int | None,
        search_query: NormalizedSearch | None = None,
        cursor: str | None = None,
        limit: int = 50,
        next_cursor: str | None = None,
        has_more: bool = False,
    ) -> None:
        if expected_generation is None:
            return

        key = make_library_cards_page_cache_key(
            user_id=user_id,
            generation=expected_generation,
            search_query=search_query,
            cursor=cursor,
            limit=limit,
        )

        cached_page = CursorPage[int](
            items=card_ids,
            next_cursor=next_cursor,
            has_more=has_more,
        )

        await self._redis_set(
            key=key,
            value=cached_page.model_dump_json(),
            ex=LIBRARY_PAGE_TTL,
        )

    @traced("redis.cache.get_cached_library_cards_page")
    async def get_cached_library_cards_page(
        self,
        user_id: int,
        search_query: NormalizedSearch | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> LibraryPageCacheLookup:
        """
        returns cached page and generation \n
        if page is None - no cache \n
        if generation is None - stored generation is invalid
        """
        generation = await self._get_library_cards_page_generation(
            user_id=user_id,
        )

        # invalid generation
        if generation is None:
            return LibraryPageCacheLookup(
                page=None,
                generation=None,
            )

        key = make_library_cards_page_cache_key(
            user_id=user_id,
            generation=generation,
            search_query=search_query,
            cursor=cursor,
            limit=limit,
        )

        value = await self._redis_get(
            key=key,
        )

        # no cache
        if value is None:
            return LibraryPageCacheLookup(
                page=None,
                generation=generation,
            )

        cached = self._deserialize_cached_value(
            key=key,
            value=value,
            deserializer=CursorPage[int].model_validate_json,
        )

        # error in deserializing
        if cached is None:
            await self._redis_delete(key=key)
            return LibraryPageCacheLookup(
                page=None,
                generation=generation,
            )

        return LibraryPageCacheLookup(
            page=cached,
            generation=generation,
        )

    @traced("redis.cache.cache_library_decks_page")
    async def cache_library_decks_page(
        self,
        user_id: int,
        deck_ids: list[int],
        next_cursor: str | None,
        has_more: bool,
        expected_generation: int | None,
        search_query: NormalizedSearch | None = None,
        is_favourite: bool = False,
        cursor: str | None = None,
        limit: int = 50,
    ) -> None:
        if expected_generation is None:
            return
        
        key = make_library_deck_page_cache_key(
            user_id=user_id,
            generation=expected_generation,
            search_query=search_query,
            is_favourite=is_favourite,
            cursor=cursor,
            limit=limit,
        )

        cached_page = CursorPage[int](
            items=deck_ids,
            next_cursor=next_cursor,
            has_more=has_more,
        )
        await self._redis_set(
            key=key,
            value=cached_page.model_dump_json(),
            ex=LIBRARY_PAGE_TTL,
        )

    @traced("redis.cache.get_cached_library_decks_page")
    async def get_cached_library_decks_page(
        self,
        user_id: int,
        search_query: NormalizedSearch | None = None,
        is_favourite: bool = False,
        cursor: str | None = None,
        limit: int = 50,
    ) -> LibraryPageCacheLookup:
        """
        returns cached page and generation \n
        if page is None - no cache \n
        if generation is None - stored generation is invalid
        """
        generation = await self._get_library_deck_page_generation(
            user_id=user_id,
        )

        # invalid generation
        if generation is None:
            return LibraryPageCacheLookup(
                page=None,
                generation=None,
            )
        
        key = make_library_deck_page_cache_key(
            user_id=user_id,
            generation=generation,
            search_query=search_query,
            is_favourite=is_favourite,
            cursor=cursor,
            limit=limit,
        )

        value = await self._redis_get(
            key=key,
        )

        # no cache
        if value is None:
            return LibraryPageCacheLookup(
                page=None,
                generation=generation,
            )

        cached = self._deserialize_cached_value(
            key=key,
            value=value,
            deserializer=CursorPage[int].model_validate_json,
        )

        if cached is None:
            await self._redis_delete(
                key=key,
            )
            return LibraryPageCacheLookup(
                page=None,
                generation=generation,
            )

        result = LibraryPageCacheLookup(
            page=cached,
            generation=generation,
        )
        return result

    @traced("redis.cache.cache_deck_cards")
    async def cache_deck_cards(
        self,
        deck_cards: dict[int, list[int]],
    ) -> None:
        if not deck_cards:
            return

        keys: list[str] = []
        values: list[bytes] = []

        for deck_id, card_ids in deck_cards.items():
            keys.append(
                make_deck_cards_cache_key(deck_id=deck_id)
            )
            values.append(
                orjson.dumps(card_ids)
            )

        await self._redis_set_many(
            entries=dict(zip(keys, values, strict=True)),
            ex=DECK_CARDS_TTL,
        )

    @traced("redis.cache.get_cached_deck_cards")
    async def get_cached_deck_cards(
        self,
        deck_ids: list[int],
    ) -> CacheLookupResult[int, list[int]]:
        result = await self._get_many(
            identities=deck_ids,
            key_factory=make_deck_cards_cache_key,
            deserializer=self._deserialize_id_list,
        )
        return result

    @traced("redis.cache.cache_cards")
    async def cache_cards(
        self,
        cards: list[InternalCard],
    ) -> None:
        if not cards:
            return

        keys: list[str] = [
            make_card_cache_key(
                card_id=card.id,
            )
            for card in cards
        ]

        values: list[str] = [
            card.model_dump_json()
            for card in cards
        ]

        await self._redis_set_many(
            entries=dict(zip(keys, values, strict=True)),
            ex=CARD_TTL,
        )

        await self._cache_ids_by_uuids(
            entity_uuids=[card.uuid for card in cards],
            entity_ids=[card.id for card in cards],
            key_factory=make_card_uuid_cache_key,
            ttl=CARD_ID_BY_UUID_TTL,
        )

    @traced("redis.cache.get_cached_cards")
    async def get_cached_cards(
        self,
        card_ids: list[int],
    ) -> CacheLookupResult[int, InternalCard]:
        result = await self._get_many(
            identities=card_ids,
            key_factory=make_card_cache_key,
            deserializer=InternalCard.model_validate_json,
        )
        return result

    async def get_cached_cards_by_uuids(
        self,
        card_uuids: list[UUID],
    ) -> CacheLookupResult[UUID, InternalCard]:
        return await self._get_cached_entities_by_uuids(
            entity_uuids=card_uuids,
            uuid_key_factory=make_card_uuid_cache_key,
            entity_key_factory=make_card_cache_key,
            entity_deserializer=InternalCard.model_validate_json,
        )

    @traced("redis.cache.cache_decks")
    async def cache_decks(
        self,
        decks: list[InternalDeck],
    ) -> None:
        if not decks:
            return

        keys: list[str] = [
            make_deck_cache_key(
                deck_id=deck.id,
            )
            for deck in decks
        ]

        values: list[str] = [
            deck.model_dump_json()
            for deck in decks
        ]

        await self._redis_set_many(
            entries=dict(zip(keys, values, strict=True)),
            ex=DECK_TTL,
        )

        await self._cache_ids_by_uuids(
            entity_uuids=[deck.uuid for deck in decks],
            entity_ids=[deck.id for deck in decks],
            key_factory=make_deck_uuid_cache_key,
            ttl=DECK_ID_BY_UUID_TTL,
        )

    @traced("redis.cache.get_cached_decks")
    async def get_cached_decks(
        self,
        deck_ids: list[int],
    ) -> CacheLookupResult[int, InternalDeck]:
        result = await self._get_many(
            identities=deck_ids,
            key_factory=make_deck_cache_key,
            deserializer=InternalDeck.model_validate_json,
        )
        return result

    async def get_cached_decks_by_uuids(
        self,
        deck_uuids: list[UUID],
    ) -> CacheLookupResult[UUID, InternalDeck]:
        return await self._get_cached_entities_by_uuids(
            entity_uuids=deck_uuids,
            uuid_key_factory=make_deck_uuid_cache_key,
            entity_key_factory=make_deck_cache_key,
            entity_deserializer=InternalDeck.model_validate_json,
        )

    async def _get_many[K: Hashable, T](
        self,
        identities: list[K],
        key_factory: Callable[[K], str],
        deserializer: Callable[[bytes | str], T],
    ) -> CacheLookupResult[K, T]:
        if not identities:
            return CacheLookupResult(
                cached={},
                missing=[],
            )

        keys = [
            key_factory(identity)
            for identity in identities
        ]
        values = await self._redis_mget(
            keys=keys,
        )

        cached: dict[K, T] = {}
        missing: list[K] = []
        corrupted_keys: list[str] = []

        for identity, key, value in zip(identities, keys, values):
            if value is None:
                missing.append(identity)
                continue

            item = self._deserialize_cached_value(
                key=key,
                value=value,
                deserializer=deserializer,
            )

            if item is None:
                missing.append(identity)
                corrupted_keys.append(key)
                continue

            cached[identity] = item

        await self._redis_delete_many(
            keys=corrupted_keys,
        )

        return CacheLookupResult(
            cached=cached,
            missing=missing,
        )
