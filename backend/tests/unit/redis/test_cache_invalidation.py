from unittest.mock import call

import pytest
from redis.exceptions import ConnectionError

from app.decks.utils import make_user_deck_identity
from app.redis.invalidation import CacheInvalidator, DelKey, scopes
from tests.unit.redis.cases import CARD_UUID, DECK_UUID, USER_UUID


@pytest.mark.parametrize(("scope_fn", "identity", "key"), [
    (scopes.users, 42, "user:42"),
    (scopes.users_settings, 42, "user:42:settings"),
    (scopes.cards, 100, "card:100"),
    (scopes.decks, 200, "deck:200"),
    (scopes.deck_cards, 200, "deck:200:card-ids"),
    (scopes.user_decks, make_user_deck_identity(42, 200), "deck:user-deck:42:200"),
    (scopes.user_ids_by_uuids, USER_UUID, f"user:id-by-uuid:{USER_UUID}"),
    (scopes.card_ids_by_uuids, CARD_UUID, f"card:id-by-uuid:{CARD_UUID}"),
    (scopes.deck_ids_by_uuids, DECK_UUID, f"deck:id-by-uuid:{DECK_UUID}"),
])
class TestInvalidateEntries:
    async def test_unlinks_requested_cache_key(
        self, redis_client, redis_pipeline, scope_fn, identity, key,
    ):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate(scope_fn(identity))

        redis_client.pipeline.assert_called_once_with(transaction=False)
        redis_pipeline.unlink.assert_called_once_with(key)
        redis_pipeline.execute.assert_awaited_once_with()

    async def test_does_not_contact_redis_for_empty_scope(
        self, redis_client, scope_fn, identity, key,
    ):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate(scope_fn())

        redis_client.pipeline.assert_not_called()

    async def test_propagates_original_redis_error(
        self, redis_client, redis_pipeline, scope_fn, identity, key,
    ):
        invalidator = CacheInvalidator(redis_client)
        failure = ConnectionError("Redis unavailable")
        redis_pipeline.execute.side_effect = failure

        with pytest.raises(ConnectionError) as error:
            await invalidator.invalidate(scope_fn(identity))

        assert error.value is failure
        redis_pipeline.unlink.assert_called_once_with(key)
        redis_pipeline.execute.assert_awaited_once_with()


@pytest.mark.parametrize(("scope_fn", "kind"), [
    (scopes.library_card_pages, "cards"),
    (scopes.library_deck_pages, "decks"),
])
class TestInvalidateLibraryPages:
    async def test_advances_each_users_generation_without_expiration(
        self, redis_client, redis_pipeline, scope_fn, kind,
    ):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate(scope_fn(42, 43))

        redis_client.pipeline.assert_called_once_with(transaction=False)
        assert redis_pipeline.method_calls == [
            call.incr(f"library:42:{kind}:generation"),
            call.incr(f"library:43:{kind}:generation"),
            call.execute(),
        ]
        redis_pipeline.execute.assert_awaited_once_with()
        redis_pipeline.unlink.assert_not_called()
        # Истёкший счётчик начался бы заново и совпал с ещё живой страницей.
        redis_pipeline.expire.assert_not_called()

    async def test_does_not_contact_redis_for_empty_scope(
        self, redis_client, scope_fn, kind,
    ):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate(scope_fn())

        redis_client.pipeline.assert_not_called()

    @pytest.mark.parametrize("failure_stage", ["pipeline", "incr", "execute"])
    async def test_propagates_original_generation_invalidation_error(
        self, redis_client, redis_pipeline, scope_fn, kind, failure_stage,
    ):
        invalidator = CacheInvalidator(redis_client)
        target = redis_client.pipeline if failure_stage == "pipeline" else getattr(
            redis_pipeline, failure_stage,
        )
        failure = ConnectionError("Redis unavailable")
        target.side_effect = failure

        with pytest.raises(ConnectionError) as error:
            await invalidator.invalidate(scope_fn(42))

        assert error.value is failure


class TestCacheInvalidatorInvalidate:
    async def test_executes_explicit_scopes_and_deduplicates_overlapping_operations(
        self, redis_client, redis_pipeline,
    ):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate(
            scopes.cards(100, 100),
            scopes.deck_with_cards(200, 201),
            scopes.decks(200),
            scopes.library(42, 43),
            scopes.library_deck_pages(42),
            scopes.user_decks(
                make_user_deck_identity(42, 200),
                make_user_deck_identity(43, 201),
            ),
        )

        assert redis_pipeline.method_calls == [
            call.unlink(
                "card:100", "deck:200", "deck:201",
                "deck:200:card-ids", "deck:201:card-ids",
                "deck:user-deck:42:200", "deck:user-deck:43:201",
            ),
            call.incr("library:42:decks:generation"),
            call.incr("library:43:decks:generation"),
            call.incr("library:42:cards:generation"),
            call.incr("library:43:cards:generation"),
            call.execute(),
        ]

    async def test_accepts_materialized_operations_alongside_scopes(
        self, redis_client, redis_pipeline,
    ):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate([DelKey("card:100")], scopes.cards(100, 101))

        redis_pipeline.unlink.assert_called_once_with("card:100", "card:101")
        redis_pipeline.execute.assert_awaited_once_with()

    async def test_does_not_contact_redis_without_groups(self, redis_client):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate()

        redis_client.pipeline.assert_not_called()

    @pytest.mark.parametrize(("card_count", "expected_batch_sizes"), [
        (1, [1]),
        (500, [500]),
        (501, [500, 1]),
        (1000, [500, 500]),
        (1001, [500, 500, 1]),
    ])
    async def test_unlinks_keys_in_batches_of_at_most_500(
        self, redis_client, redis_pipeline, card_count, expected_batch_sizes,
    ):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate(scopes.cards(*range(1, card_count + 1)))

        calls = redis_pipeline.unlink.call_args_list
        assert [len(item.args) for item in calls] == expected_batch_sizes
        assert calls[0].args[0] == "card:1"
        assert calls[-1].args[-1] == f"card:{card_count}"
        redis_pipeline.execute.assert_awaited_once_with()
