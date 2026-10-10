from unittest.mock import call, create_autospec

import pytest
from redis.exceptions import ConnectionError

from app.redis.invalidation import CacheInvalidator, scopes
from app.redis.outbox import CacheInvalidationHandler
from tests.unit.redis.cases import CARD_UUID


class TestCacheInvalidationHandler:
    async def test_passes_loaded_scopes_as_separate_arguments_to_invalidator(self):
        invalidator = create_autospec(CacheInvalidator, instance=True)
        handler = CacheInvalidationHandler(invalidator)

        await handler({"scopes": [
            {"name": "cards", "args": [100]},
            {"name": "library_card_pages", "args": [42]},
        ]})

        invalidator.invalidate.assert_awaited_once_with(
            scopes.cards(100), scopes.library_card_pages(42),
        )

    async def test_delivers_scopes_from_jsonb_payload(self, redis_client, redis_pipeline):
        handler = CacheInvalidationHandler(CacheInvalidator(redis_client))

        await handler({"scopes": [
            {"name": "cards_removed", "args": [{"id": 100, "uuid": str(CARD_UUID)}]},
            {"name": "user_decks", "args": [[42, 200]]},
            {"name": "library_card_pages", "args": [42]},
        ]})

        assert redis_pipeline.method_calls == [
            call.unlink("card:100", f"card:id-by-uuid:{CARD_UUID}", "deck:user-deck:42:200"),
            call.incr("library:42:cards:generation"),
            call.execute(),
        ]

    async def test_propagates_redis_failure(self, redis_client, redis_pipeline):
        handler = CacheInvalidationHandler(CacheInvalidator(redis_client))
        redis_pipeline.execute.side_effect = ConnectionError("Redis unavailable")

        with pytest.raises(ConnectionError):
            await handler({"scopes": [{"name": "library", "args": [42]}]})

        redis_pipeline.execute.assert_awaited_once_with()

    async def test_rejects_unknown_scope_before_redis(self, redis_client):
        handler = CacheInvalidationHandler(CacheInvalidator(redis_client))

        with pytest.raises(ValueError, match="Unknown cache scope"):
            await handler({"scopes": [
                {"name": "cards", "args": [100]},
                {"name": "unknown", "args": []},
            ]})

        redis_client.pipeline.assert_not_called()

    async def test_empty_payload_does_not_contact_redis(self, redis_client):
        handler = CacheInvalidationHandler(CacheInvalidator(redis_client))

        await handler({"scopes": []})

        redis_client.pipeline.assert_not_called()
