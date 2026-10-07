from unittest.mock import call

import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError

from app.redis.outbox import (
    ExpiredArchivedDecksCacheInvalidationHandler,
    ExpiredArchivedDecksCacheInvalidationPayload,
)
from app.redis.service import RedisCacheService
from tests.unit.redis.cases import CARD_UUID, DECK_UUID


class TestExpiredArchivedDecksCacheInvalidationPayload:
    def test_serializes_uuid_and_compound_keys_as_json_values(self):
        payload = ExpiredArchivedDecksCacheInvalidationPayload(
            deck_ids=[200], deck_uuids=[DECK_UUID],
            card_ids=[100], card_uuids=[CARD_UUID], user_deck_keys=[(42, 200)],
        )

        data = payload.model_dump(mode="json")

        assert data == {
            "deck_ids": [200], "deck_uuids": [str(DECK_UUID)],
            "card_ids": [100], "card_uuids": [str(CARD_UUID)],
            "user_deck_keys": [[42, 200]],
        }

    @pytest.mark.parametrize("payload", [
        {"deck_ids": [0]}, {"card_ids": [-1]}, {"deck_uuids": ["invalid"]},
        {"user_deck_keys": [[0, 200]]}, {"unknown_field": []},
    ])
    def test_rejects_invalid_payload(self, payload):
        with pytest.raises(ValidationError):
            ExpiredArchivedDecksCacheInvalidationPayload.model_validate(payload)


class TestExpiredArchivedDecksCacheInvalidationHandler:
    def test_rejects_cache_that_swallows_delivery_errors(self, cache_service):
        with pytest.raises(ValueError, match="raise_errors=True"):
            ExpiredArchivedDecksCacheInvalidationHandler(cache_service)

    async def test_deletes_all_cache_keys_from_persisted_payload(self, redis_client):
        handler = ExpiredArchivedDecksCacheInvalidationHandler(
            RedisCacheService(redis_client, raise_errors=True),
        )

        await handler({
            "deck_ids": [200], "deck_uuids": [str(DECK_UUID)],
            "card_ids": [100], "card_uuids": [str(CARD_UUID)],
            "user_deck_keys": [[42, 200]],
        })

        assert redis_client.delete.await_args_list == [
            call("deck:200"), call(f"deck:id-by-uuid:{DECK_UUID}"),
            call("deck:200:card-ids"), call("deck:user-deck:42:200"),
            call("card:100"), call(f"card:id-by-uuid:{CARD_UUID}"),
        ]

    async def test_replays_complete_event_after_partial_redis_failure(self, redis_client):
        handler = ExpiredArchivedDecksCacheInvalidationHandler(
            RedisCacheService(redis_client, raise_errors=True),
        )
        redis_client.delete.side_effect = [1, ConnectionError("Redis unavailable")]
        payload = {"deck_ids": [200], "deck_uuids": [str(DECK_UUID)]}

        with pytest.raises(ConnectionError):
            await handler(payload)
        redis_client.delete.side_effect = None
        await handler(payload)

        assert redis_client.delete.await_args_list == [
            call("deck:200"), call(f"deck:id-by-uuid:{DECK_UUID}"),
            call("deck:200"), call(f"deck:id-by-uuid:{DECK_UUID}"),
            call("deck:200:card-ids"),
        ]
