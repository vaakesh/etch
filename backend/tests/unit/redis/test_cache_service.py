from unittest.mock import ANY, AsyncMock, MagicMock, call
from uuid import UUID

import pytest

from app.cards.schemas import InternalCard
from app.decks.schemas import InternalDeck
from app.redis.service import (
    CARD_ID_BY_UUID_TTL,
    CARD_TTL,
    DECK_ID_BY_UUID_TTL,
    DECK_TTL,
    USER_ID_BY_UUID,
    USER_TTL,
    RedisCacheService,
)
from app.users.schemas import InternalUser
from tests.unit.factories import make_card, make_deck, make_user


class TestCacheEntities:
    @pytest.mark.parametrize(
        (
            "method_name",
            "entity",
            "entity_key",
            "entity_ttl",
            "uuid_key",
            "uuid_ttl",
        ),
        [
            pytest.param(
                "cache_users",
                InternalUser.model_validate(make_user()),
                "user:42",
                USER_TTL,
                "user:id-by-uuid:12345678-1234-5678-1234-567812345678",
                USER_ID_BY_UUID,
                id="users",
            ),
            pytest.param(
                "cache_cards",
                InternalCard.model_validate(make_card()),
                "card:100",
                CARD_TTL,
                "card:id-by-uuid:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                CARD_ID_BY_UUID_TTL,
                id="cards",
            ),
            pytest.param(
                "cache_decks",
                InternalDeck.model_validate(make_deck()),
                "deck:200",
                DECK_TTL,
                "deck:id-by-uuid:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                DECK_ID_BY_UUID_TTL,
                id="decks",
            ),
        ],
    )
    async def test_caches_entity_and_uuid_index(
        self,
        method_name,
        entity,
        entity_key,
        entity_ttl,
        uuid_key,
        uuid_ttl,
    ):
        redis = MagicMock()
        entity_pipeline = MagicMock()
        entity_pipeline.execute = AsyncMock()
        uuid_pipeline = MagicMock()
        uuid_pipeline.execute = AsyncMock()
        redis.pipeline.side_effect = [entity_pipeline, uuid_pipeline]
        cache_service = RedisCacheService(redis=redis)
        cache_service.with_jitter = lambda base, spread=300: base

        await getattr(cache_service, method_name)([entity])

        assert redis.pipeline.call_args_list == [
            call(transaction=False),
            call(transaction=False),
        ]
        entity_pipeline.set.assert_called_once_with(
            name=entity_key,
            value=ANY,
            ex=entity_ttl,
        )
        uuid_pipeline.set.assert_called_once_with(
            name=uuid_key,
            value=str(entity.id),
            ex=uuid_ttl,
        )
        entity_pipeline.execute.assert_awaited_once_with()
        uuid_pipeline.execute.assert_awaited_once_with()


class TestGetCachedEntitiesByUuids:
    @pytest.mark.parametrize(
        (
            "method_name",
            "entity",
            "uuid_key",
            "entity_key",
        ),
        [
            pytest.param(
                "get_cached_users_by_uuids",
                InternalUser.model_validate(make_user()),
                "user:id-by-uuid:12345678-1234-5678-1234-567812345678",
                "user:42",
                id="users",
            ),
            pytest.param(
                "get_cached_cards_by_uuids",
                InternalCard.model_validate(make_card()),
                "card:id-by-uuid:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "card:100",
                id="cards",
            ),
            pytest.param(
                "get_cached_decks_by_uuids",
                InternalDeck.model_validate(make_deck()),
                "deck:id-by-uuid:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "deck:200",
                id="decks",
            ),
        ],
    )
    async def test_returns_entities_keyed_by_uuid(
        self,
        method_name,
        entity,
        uuid_key,
        entity_key,
    ):
        redis = AsyncMock()
        redis.mget.side_effect = [
            [str(entity.id)],
            [entity.model_dump_json()],
        ]
        cache_service = RedisCacheService(redis=redis)

        lookup = await getattr(cache_service, method_name)([entity.uuid])

        assert lookup.cached == {entity.uuid: entity}
        assert lookup.missing == []
        assert redis.mget.await_args_list == [
            call(keys=[uuid_key]),
            call(keys=[entity_key]),
        ]

    async def test_returns_uuid_as_missing_when_id_is_not_cached(self):
        user_uuid = UUID("12345678-1234-5678-1234-567812345678")
        redis = AsyncMock()
        redis.mget.return_value = [None]
        cache_service = RedisCacheService(redis=redis)

        lookup = await cache_service.get_cached_users_by_uuids(
            user_uuids=[user_uuid],
        )

        assert lookup.cached == {}
        assert lookup.missing == [user_uuid]
        redis.mget.assert_awaited_once_with(
            keys=[f"user:id-by-uuid:{user_uuid}"],
        )

    async def test_returns_uuid_as_missing_when_entity_is_not_cached(self):
        user_uuid = UUID("12345678-1234-5678-1234-567812345678")
        redis = AsyncMock()
        redis.mget.side_effect = [["42"], [None]]
        cache_service = RedisCacheService(redis=redis)

        lookup = await cache_service.get_cached_users_by_uuids(
            user_uuids=[user_uuid],
        )

        assert lookup.cached == {}
        assert lookup.missing == [user_uuid]
        assert redis.mget.await_args_list == [
            call(keys=[f"user:id-by-uuid:{user_uuid}"]),
            call(keys=["user:42"]),
        ]

    async def test_returns_uuid_as_missing_when_cached_entity_has_other_uuid(
        self,
    ):
        requested_uuid = UUID("12345678-1234-5678-1234-567812345679")
        cached_user = InternalUser.model_validate(make_user())
        redis = AsyncMock()
        redis.mget.side_effect = [
            [str(cached_user.id)],
            [cached_user.model_dump_json()],
        ]
        cache_service = RedisCacheService(redis=redis)

        lookup = await cache_service.get_cached_users_by_uuids(
            user_uuids=[requested_uuid],
        )

        assert lookup.cached == {}
        assert lookup.missing == [requested_uuid]
