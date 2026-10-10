from unittest.mock import Mock, call

import orjson
import pytest
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from app.redis.service import RedisCacheService
from tests.unit.redis.cases import (
    CACHE_CASES,
    OTHER_UUID,
    USER_DECK_DATA,
    UUID_CASES,
    cache_kwargs,
    dump_cached,
    get_kwargs,
)


@pytest.mark.parametrize("case", CACHE_CASES, ids=lambda case: case.name)
class TestCacheEntities:
    async def test_stores_complete_payload_with_ttl_and_uuid_index(
        self, cache_service, redis_client, redis_pipeline, case,
    ):
        await getattr(cache_service, case.cache_method)(**cache_kwargs(case))

        entity_write = redis_pipeline.set.call_args_list[0].kwargs
        assert entity_write["name"] == case.key
        assert orjson.loads(entity_write["value"]) == case.payload
        assert entity_write["ex"] == case.ttl + 17
        if case.uuid is not None:
            assert redis_pipeline.set.call_args_list[1:] == [call(
                name=case.uuid_key, value=str(case.identity), ex=604817,
            )]
            assert redis_pipeline.execute.await_count == 2
        else:
            assert redis_pipeline.set.call_count == 1
            redis_pipeline.execute.assert_awaited_once_with()
        redis_client.pipeline.assert_called_with(transaction=False)

    async def test_does_not_contact_redis_for_empty_input(
        self, cache_service, redis_client, case,
    ):
        await getattr(cache_service, case.cache_method)(**cache_kwargs(case, empty=True))

        assert redis_client.mock_calls == []

    @pytest.mark.parametrize("failure_stage", ["pipeline", "set", "execute"])
    async def test_propagates_redis_error_when_write_fails(
        self, cache_service, redis_client, redis_pipeline, case, failure_stage,
    ):
        target = redis_client.pipeline if failure_stage == "pipeline" else getattr(
            redis_pipeline, failure_stage,
        )
        failure = ConnectionError("Redis unavailable")
        target.side_effect = failure

        with pytest.raises(ConnectionError) as error:
            await getattr(cache_service, case.cache_method)(**cache_kwargs(case))

        assert error.value is failure


@pytest.mark.parametrize("case", CACHE_CASES, ids=lambda case: case.name)
class TestGetCachedEntities:
    @pytest.mark.parametrize("as_bytes", [False, True], ids=["string", "bytes"])
    async def test_returns_complete_cached_payload(
        self, cache_service, redis_client, case, as_bytes,
    ):
        value = orjson.dumps(case.payload)
        redis_client.mget.return_value = [value if as_bytes else value.decode()]

        result = await getattr(cache_service, case.get_method)(**get_kwargs(case))

        assert {key: dump_cached(value) for key, value in result.cached.items()} == {
            case.identity: case.payload,
        }
        assert result.missing == []
        redis_client.mget.assert_awaited_once_with(keys=[case.key])
        redis_client.delete.assert_not_awaited()

    async def test_returns_missing_identity_without_deleting_absent_key(
        self, cache_service, redis_client, case,
    ):
        redis_client.mget.return_value = [None]

        result = await getattr(cache_service, case.get_method)(**get_kwargs(case))

        assert result.cached == {}
        assert result.missing == [case.identity]
        redis_client.delete.assert_not_awaited()

    @pytest.mark.parametrize("value", ["not-json", "{}", "null"])
    async def test_treats_corrupted_value_as_miss_and_deletes_it(
        self, cache_service, redis_client, case, value,
    ):
        redis_client.mget.return_value = [value]

        result = await getattr(cache_service, case.get_method)(**get_kwargs(case))

        assert result.cached == {}
        assert result.missing == [case.identity]
        redis_client.delete.assert_awaited_once_with(case.key)

    async def test_propagates_redis_error_when_corrupted_value_cannot_be_deleted(
        self, cache_service, redis_client, case,
    ):
        redis_client.mget.return_value = ["not-json"]
        failure = TimeoutError("Redis unavailable")
        redis_client.delete.side_effect = failure

        with pytest.raises(TimeoutError) as error:
            await getattr(cache_service, case.get_method)(**get_kwargs(case))

        assert error.value is failure
        redis_client.delete.assert_awaited_once_with(case.key)

    async def test_propagates_redis_error_when_read_fails(
        self, cache_service, redis_client, case,
    ):
        failure = RedisError("Redis unavailable")
        redis_client.mget.side_effect = failure

        with pytest.raises(RedisError) as error:
            await getattr(cache_service, case.get_method)(**get_kwargs(case))

        assert error.value is failure
        redis_client.delete.assert_not_awaited()

    async def test_does_not_contact_redis_for_empty_input(
        self, cache_service, redis_client, case,
    ):
        result = await getattr(cache_service, case.get_method)(**get_kwargs(case, empty=True))

        assert result.cached == {}
        assert result.missing == []
        assert redis_client.mock_calls == []


@pytest.mark.parametrize("case", UUID_CASES, ids=lambda case: case.name)
class TestGetCachedEntitiesByUuids:
    async def test_returns_payload_keyed_by_requested_uuid(
        self, cache_service, redis_client, case,
    ):
        redis_client.mget.side_effect = [[str(case.identity)], [orjson.dumps(case.payload)]]

        result = await getattr(cache_service, case.uuid_get_method)([case.uuid])

        assert {key: dump_cached(value) for key, value in result.cached.items()} == {
            case.uuid: case.payload,
        }
        assert result.missing == []
        assert redis_client.mget.await_args_list == [
            call(keys=[case.uuid_key]), call(keys=[case.key]),
        ]

    async def test_returns_miss_without_reading_entities_when_index_is_absent(
        self, cache_service, redis_client, case,
    ):
        redis_client.mget.return_value = [None]

        result = await getattr(cache_service, case.uuid_get_method)([case.uuid])

        assert result.cached == {}
        assert result.missing == [case.uuid]
        redis_client.mget.assert_awaited_once_with(keys=[case.uuid_key])

    async def test_deletes_invalid_uuid_index_and_returns_miss(
        self, cache_service, redis_client, case,
    ):
        redis_client.mget.return_value = ["not-an-id"]

        result = await getattr(cache_service, case.uuid_get_method)([case.uuid])

        assert result.cached == {}
        assert result.missing == [case.uuid]
        redis_client.delete.assert_awaited_once_with(case.uuid_key)
        redis_client.mget.assert_awaited_once_with(keys=[case.uuid_key])

    async def test_returns_miss_when_entity_is_absent(
        self, cache_service, redis_client, case,
    ):
        redis_client.mget.side_effect = [[str(case.identity)], [None]]

        result = await getattr(cache_service, case.uuid_get_method)([case.uuid])

        assert result.cached == {}
        assert result.missing == [case.uuid]
        redis_client.delete.assert_not_awaited()

    async def test_rejects_entity_with_different_uuid(
        self, cache_service, redis_client, case,
    ):
        redis_client.mget.side_effect = [[str(case.identity)], [orjson.dumps(case.payload)]]

        result = await getattr(cache_service, case.uuid_get_method)([OTHER_UUID])

        assert result.cached == {}
        assert result.missing == [OTHER_UUID]
        assert redis_client.mget.await_args_list == [
            call(keys=[f"{case.name[:-1]}:id-by-uuid:{OTHER_UUID}"]),
            call(keys=[case.key]),
        ]

    @pytest.mark.parametrize("failure_stage", ["index", "entity"])
    async def test_propagates_redis_error_when_read_fails(
        self, cache_service, redis_client, case, failure_stage,
    ):
        failure = ConnectionError("Redis unavailable")
        redis_client.mget.side_effect = [failure] if failure_stage == "index" else [
            [str(case.identity)], failure,
        ]

        with pytest.raises(ConnectionError) as error:
            await getattr(cache_service, case.uuid_get_method)([case.uuid])

        assert error.value is failure

    async def test_reads_same_entity_once_for_duplicate_uuid_indices(
        self, cache_service, redis_client, case,
    ):
        redis_client.mget.side_effect = [
            [str(case.identity), str(case.identity)], [orjson.dumps(case.payload)],
        ]

        result = await getattr(cache_service, case.uuid_get_method)([case.uuid, OTHER_UUID])

        assert {key: dump_cached(value) for key, value in result.cached.items()} == {
            case.uuid: case.payload,
        }
        assert result.missing == [OTHER_UUID]
        assert redis_client.mget.await_args_list[1] == call(keys=[case.key])

    async def test_does_not_contact_redis_for_empty_input(
        self, cache_service, redis_client, case,
    ):
        result = await getattr(cache_service, case.uuid_get_method)([])

        assert result.cached == {}
        assert result.missing == []
        assert redis_client.mock_calls == []


class TestGetCachedDeckCards:
    @pytest.mark.parametrize("value", ['[true]', '["100"]', '[1.5]', '[null]'])
    async def test_rejects_non_integer_card_ids(self, cache_service, redis_client, value):
        redis_client.mget.return_value = [value]

        result = await cache_service.get_cached_deck_cards([200])

        assert result.cached == {}
        assert result.missing == [200]
        redis_client.delete.assert_awaited_once_with("deck:200:card-ids")

    async def test_preserves_hits_and_miss_order_while_removing_only_corrupted_keys(
        self, cache_service, redis_client,
    ):
        redis_client.mget.return_value = ["[100,101]", None, "{}", "[]"]

        result = await cache_service.get_cached_deck_cards([200, 201, 202, 203])

        assert result.cached == {200: [100, 101], 203: []}
        assert result.missing == [201, 202]
        redis_client.mget.assert_awaited_once_with(keys=[
            "deck:200:card-ids", "deck:201:card-ids",
            "deck:202:card-ids", "deck:203:card-ids",
        ])
        redis_client.delete.assert_awaited_once_with("deck:202:card-ids")

    async def test_caches_empty_deck_as_empty_list(self, cache_service, redis_pipeline):
        await cache_service.cache_deck_cards({200: []})

        redis_pipeline.set.assert_called_once_with(
            name="deck:200:card-ids", value=b"[]", ex=3617,
        )
        redis_pipeline.execute.assert_awaited_once_with()


@pytest.mark.parametrize(
    "case", [case for case in CACHE_CASES if case.name in {"users", "cards", "decks", "settings"}],
    ids=lambda case: case.name,
)
class TestGetCachedEntityDates:
    async def test_removes_cached_entity_with_update_date_before_creation(
        self, cache_service, redis_client, case,
    ):
        payload = {**case.payload, "updated_at": "2019-01-01T12:00:00Z"}
        redis_client.mget.return_value = [orjson.dumps(payload)]

        result = await getattr(cache_service, case.get_method)(**get_kwargs(case))

        assert result.cached == {}
        assert result.missing == [case.identity]
        redis_client.delete.assert_awaited_once_with(case.key)


class TestGetCachedUserDecks:
    async def test_removes_cached_state_with_answers_without_completed_sessions(
        self, cache_service, redis_client,
    ):
        redis_client.mget.return_value = [orjson.dumps({**USER_DECK_DATA, "correct_count": 1})]

        result = await cache_service.get_cached_user_decks(user_id=42, deck_ids=[200])

        assert result.cached == {}
        assert result.missing == [(42, 200)]
        redis_client.delete.assert_awaited_once_with("deck:user-deck:42:200")


class TestWithJitter:
    @pytest.mark.parametrize(("base", "spread", "offset", "expected"), [
        (300, 300, 0, 300), (300, 300, 300, 600), (60, 0, 0, 60),
    ])
    def test_adds_random_offset_within_requested_range(
        self, monkeypatch, base, spread, offset, expected,
    ):
        randint = Mock(return_value=offset)
        monkeypatch.setattr("app.redis.service.random.randint", randint)

        result = RedisCacheService.with_jitter(base=base, spread=spread)

        assert result == expected
        randint.assert_called_once_with(0, spread)
