import logging
from collections.abc import Callable, Hashable
import random
from uuid import UUID

import orjson
from app.cards.models import Card
from app.decks.models import Deck, UserDeck
from app.redis.keys import (
    make_card_cache_key,
    make_deck_cache_key,
    make_deck_cards_cache_key,
    make_library_cards_page_cache_key,
    make_library_cards_page_generation_cache_key,
    make_library_deck_page_cache_key,
    make_library_deck_page_generation_cache_key,
    make_user_deck_cache_key,
)
from app.redis.schemas import CacheLookupResult, LibraryPageCacheLookup, UserDeckIdentity
from app.users.schemas import NormalizedSearch
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.cards.schemas import InternalCard
from app.decks.schemas import InternalDeck, InternalUserDeck
from app.common.schemas import CursorPage

LIBRARY_PAGE_TTL = 60 * 5
GENERATION_TTL = LIBRARY_PAGE_TTL * 3
DECK_CARDS_TTL = 60 * 60
CARD_TTL = 60 * 30
DECK_TTL = 60 * 30
USER_DECK_TTL = 60 * 10

logger = logging.getLogger(__name__)


class RedisCacheService:
    """
    Best-effort Redis cache.
    Redis failures must not affect application correctness.
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

    async def _safe_set(
        self,
        *,
        key: str,
        value: bytes | str,
        ex: int,
    ) -> None:
        try:
            await self.redis.set(
                name=key,
                value=value,
                ex=self.with_jitter(base=ex),
            )
        except RedisError:
            self._log_redis_error(
                operation=f"SET {key}",
            )

    async def _safe_get(
        self,
        key: str,
    ) -> str | None:
        try:
            return await self.redis.get(key)
        except RedisError:
            self._log_redis_error(
                operation=f"GET {key}",
            )
            return

    async def _safe_set_many(
        self,
        entries: dict[str, bytes | str],
        ex: int,
    ) -> None:
        if not entries:
            return

        try:
            pipe = self.redis.pipeline(transaction=False)

            for key, value in entries.items():
                pipe.set(
                    name=key,
                    value=value,
                    ex=self.with_jitter(base=ex),
                )

            await pipe.execute()

        except RedisError:
            self._log_redis_error(
                operation=f"SET MANY {len(entries)} keys"
            )

    async def _safe_mget(
        self,
        keys: list[str],
    ) -> list[str | None] | None:
        if not keys:
            return []

        try:
            return await self.redis.mget(keys=keys)
        except RedisError:
            self._log_redis_error(
                operation=f"MGET {len(keys)}",
            )
            return

    async def _safe_delete(
        self,
        key: str,
    ) -> None:
        try:
            await self.redis.delete(key)
        except RedisError:
            self._log_redis_error(
                operation=f"DELETE {key}"
            )

    async def _safe_delete_many(
        self,
        keys: list[str],
    ) -> None:
        if not keys:
            return

        try:
            await self.redis.delete(*keys)
        except RedisError:
            self._log_redis_error(
                operation=f"DELETE {len(keys)} keys",
            )

    async def _get_page_generation(
        self,
        user_uuid: UUID,
        key_generation_factory: Callable[[UUID], str],
    ) -> int | None:
        """
        returns valid generation starting from 0
        or returns None if error has occured
        """
        key = key_generation_factory(user_uuid)

        generation = await self._safe_get(key=key)

        if generation is None:
            return 0

        try:
            return int(generation)
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
        user_uuid: UUID,
    ) -> int | None:
        """
        returns valid generation starting from 0
        or returns None if error has occured
        """
        return await self._get_page_generation(
            user_uuid=user_uuid,
            key_generation_factory=make_library_cards_page_generation_cache_key,
        )

    async def _get_library_deck_page_generation(
        self,
        user_uuid: UUID,
    ) -> int | None:
        """
        returns valid generation starting from 0
        or returns None if error has occured
        """
        return await self._get_page_generation(
            user_uuid=user_uuid,
            key_generation_factory=make_library_deck_page_generation_cache_key,
        )

    def _log_redis_error(
        self,
        operation: str,
    ) -> None:
        logger.warning(
            "Redis cache operation failed; continuing without cache",
            extra={"cache_operation": operation},
            exc_info=True,
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
        except (TypeError, ValueError):
            logger.warning(
                "Ignoring invalid cached value",
                extra={
                    "cache_key": key,
                },
                exc_info=True,
            )
            return

    @staticmethod
    def _deserialize_uuid_list(
        value: bytes | str,
    ) -> list[UUID]:
        payload = orjson.loads(value)

        if not isinstance(payload, list):
            raise ValueError("Expected a list of UUIDs")

        uuids: list[UUID] = []

        for index, item in enumerate(payload):
            if not isinstance(item, str):
                raise ValueError(
                    f"Expected UUID string at index {index}"
                )

            try:
                uuids.append(UUID(item))
            except ValueError as error:
                raise ValueError(
                    f"Invalid UUID at index {index}"
                ) from error

        return uuids


    # cache operations

    async def cache_user_decks(
        self,
        user_id: int,
        user_decks: list[UserDeck],
    ) -> None:
        entries = {
            make_user_deck_cache_key(
                identity=(user_deck.user_id, user_deck.deck_id)
            ): InternalUserDeck.model_validate(user_deck).model_dump_json()
            for user_deck in user_decks
        }

        await self._safe_set_many(
            entries=entries,
            ex=USER_DECK_TTL,
        )

    async def get_cached_user_decks(
        self,
        user_id: int,
        deck_ids: list[int],
    ) -> CacheLookupResult[UserDeckIdentity, InternalUserDeck]:
        identities: list[UserDeckIdentity] = [(user_id, deck_id) for deck_id in deck_ids]
        result = await self._get_many(
            identities=identities,
            key_factory=make_user_deck_cache_key,
            deserializer=InternalUserDeck.model_validate_json
        )
        return result

    async def invalidate_user_decks(
        self,
        identities: list[UserDeckIdentity],
    ) -> None:
        await self._invalidate_many(
            identities=identities,
            key_factory=make_user_deck_cache_key,
        )

    async def cache_library_cards_page(
        self,
        user_uuid: UUID,
        card_uuids: list[UUID],
        expected_generation: int | None,
        cursor: str | None = None,
        limit: int = 50,
        next_cursor: str | None = None,
        has_more: bool = False,
    ) -> None:
        if expected_generation is None:
            return

        key = make_library_cards_page_cache_key(
            user_uuid=user_uuid,
            generation=expected_generation,
            cursor=cursor,
            limit=limit,
        )

        cached_page = CursorPage[UUID](
            items=card_uuids,
            next_cursor=next_cursor,
            has_more=has_more,
        )

        await self._safe_set(
            key=key,
            value=cached_page.model_dump_json(),
            ex=LIBRARY_PAGE_TTL,
        )

    async def get_cached_library_cards_page(
        self,
        user_uuid: UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> LibraryPageCacheLookup:
        """
        returns cached page and generation \n
        if page is None - no cache \n
        if generation is None - error has occured
        """
        generation = await self._get_library_cards_page_generation(
            user_uuid=user_uuid,
        )

        # error
        if generation is None:
            return LibraryPageCacheLookup(
                page=None,
                generation=None,
            )

        key = make_library_cards_page_cache_key(
            user_uuid=user_uuid,
            generation=generation,
            cursor=cursor,
            limit=limit,
        )

        value = await self._safe_get(
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
            deserializer=CursorPage[UUID].model_validate_json,
        )

        # error in deserializing
        if cached is None:
            await self._safe_delete(key=key)
            return LibraryPageCacheLookup(
                page=None,
                generation=generation,
            )

        return LibraryPageCacheLookup(
            page=cached,
            generation=generation,
        )

    async def cache_library_decks_page(
        self,
        user_uuid: UUID,
        deck_uuids: list[UUID],
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
            user_uuid=user_uuid,
            generation=expected_generation,
            search_query=search_query,
            is_favourite=is_favourite,
            cursor=cursor,
            limit=limit,
        )

        cached_page = CursorPage[UUID](
            items=deck_uuids,
            next_cursor=next_cursor,
            has_more=has_more,
        )
        await self._safe_set(
            key=key,
            value=cached_page.model_dump_json(),
            ex=LIBRARY_PAGE_TTL,
        )

    async def get_cached_library_decks_page(
        self,
        user_uuid: UUID,
        search_query: NormalizedSearch | None = None,
        is_favourite: bool = False,
        cursor: str | None = None,
        limit: int = 50,
    ) -> LibraryPageCacheLookup:
        """
        returns cached page and generation \n
        if page is None - no cache \n
        if generation is None - error has occured
        """
        generation = await self._get_library_deck_page_generation(
            user_uuid=user_uuid,
        )

        # error
        if generation is None:
            return LibraryPageCacheLookup(
                page=None,
                generation=None,
            )
        
        key = make_library_deck_page_cache_key(
            user_uuid=user_uuid,
            generation=generation,
            search_query=search_query,
            is_favourite=is_favourite,
            cursor=cursor,
            limit=limit,
        )

        value = await self._safe_get(
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
            deserializer=CursorPage[UUID].model_validate_json,
        )

        if cached is None:
            await self._safe_delete(
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

    async def invalidate_cards(
        self,
        card_uuids: list[UUID],
    ) -> None:
        await self._invalidate_many(
            identities=card_uuids,
            key_factory=make_card_cache_key,
        )

    async def invalidate_decks(
        self,
        deck_uuids: list[UUID],
    ) -> None:
        await self._invalidate_many(
            identities=deck_uuids,
            key_factory=make_deck_cache_key,
        )

    async def invalidate_deck_cards(
        self,
        deck_uuids: list[UUID],
    ) -> None:
        await self._invalidate_many(
            identities=deck_uuids,
            key_factory=make_deck_cards_cache_key,
        )

    async def _invalidate_many[K](
        self,
        identities: list[K],
        key_factory: Callable[[K], str],
    ) -> None:
        if not identities:
            return

        await self._safe_delete_many(
            keys=[
                key_factory(identity)
                for identity in identities
            ]
        )

    async def invalidate_library_card_page(
        self,
        user_uuid: UUID,
    ) -> None:
        key = make_library_cards_page_generation_cache_key(
            user_uuid=user_uuid,
        )

        try:
            pipe = self.redis.pipeline(transaction=True)
            pipe.incr(key)
            pipe.expire(key, GENERATION_TTL)
            await pipe.execute()
        except RedisError:
            self._log_redis_error(
                operation=f"INCR {key}",
            )

    async def invalidate_library_deck_page(
        self,
        user_uuid: UUID,
    ) -> None:
        key = make_library_deck_page_generation_cache_key(
            user_uuid=user_uuid,
        )

        try:
            pipe = self.redis.pipeline(transaction=True)
            pipe.incr(key)
            pipe.expire(key, GENERATION_TTL)
            await pipe.execute()
        except RedisError:
            self._log_redis_error(
                operation=f"INCR {key}",
            )

    async def cache_deck_cards(
        self,
        deck_cards: dict[UUID, list[UUID]],
    ) -> None:
        if not deck_cards:
            return

        keys: list[str] = []
        values: list[bytes] = []

        for deck_uuid, card_uuids in deck_cards.items():
            keys.append(
                make_deck_cards_cache_key(deck_uuid=deck_uuid)
            )
            values.append(
                orjson.dumps(
                    [
                        str(card_uuid)
                        for card_uuid in card_uuids
                    ]
                )
            )

        await self._safe_set_many(
            entries=dict(zip(keys, values, strict=True)),
            ex=DECK_CARDS_TTL,
        )

    async def get_cached_deck_cards(
        self,
        deck_uuids: list[UUID],
    ) -> CacheLookupResult[UUID, list[UUID]]:
        result = await self._get_many(
            identities=deck_uuids,
            key_factory=make_deck_cards_cache_key,
            deserializer=self._deserialize_uuid_list,
        )
        return result

    async def cache_cards(
        self,
        cards: list[Card],
    ) -> None:
        if not cards:
            return

        keys: list[str] = [
            make_card_cache_key(
                card_uuid=card.uuid,
            )
            for card in cards
        ]

        values: list[str] = [
            InternalCard
            .from_entity(card=card)
            .model_dump_json()
            for card in cards
        ]

        await self._safe_set_many(
            entries=dict(zip(keys, values, strict=True)),
            ex=CARD_TTL,
        )

    async def get_cached_cards(
        self,
        card_uuids: list[UUID],
    ) -> CacheLookupResult[UUID, InternalCard]:
        result = await self._get_many(
            identities=card_uuids,
            key_factory=make_card_cache_key,
            deserializer=InternalCard.model_validate_json,
        )
        return result

    async def cache_decks(
        self,
        decks: list[Deck],
    ) -> None:
        if not decks:
            return

        keys: list[str] = [
            make_deck_cache_key(
                deck_uuid=deck.uuid,
            )
            for deck in decks
        ]

        values: list[str] = [
            InternalDeck
            .from_entity(deck)
            .model_dump_json()
            for deck in decks
        ]

        await self._safe_set_many(
            entries=dict(zip(keys, values, strict=True)),
            ex=DECK_TTL,
        )

    async def get_cached_decks(
        self,
        deck_uuids: list[UUID],
    ) -> CacheLookupResult[UUID, InternalDeck]:
        result = await self._get_many(
            identities=deck_uuids,
            key_factory=make_deck_cache_key,
            deserializer=InternalDeck.model_validate_json,
        )
        return result

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
        values = await self._safe_mget(
            keys=keys,
        )

        if values is None:
            return CacheLookupResult(
                cached={},
                missing=identities,
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

        await self._safe_delete_many(
            keys=corrupted_keys,
        )

        return CacheLookupResult(
            cached=cached,
            missing=missing,
        )
