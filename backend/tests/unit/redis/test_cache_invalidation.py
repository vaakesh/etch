from unittest.mock import call, create_autospec

import pytest
from redis.exceptions import ConnectionError

from app.decks.repository import DeckCardRepository, UserDeckRepository
from app.redis.service import CacheInvalidator, RedisCacheService
from tests.unit.redis.cases import CARD_UUID, DECK_UUID, USER_UUID


@pytest.mark.parametrize(("method", "argument", "identity", "key"), [
    ("invalidate_users", "user_ids", 42, "user:42"),
    ("invalidate_users_settings", "user_ids", 42, "user:42:settings"),
    ("invalidate_cards", "card_ids", 100, "card:100"),
    ("invalidate_decks", "deck_ids", 200, "deck:200"),
    ("invalidate_deck_cards", "deck_ids", 200, "deck:200:card-ids"),
    ("invalidate_user_decks", "identities", (42, 200), "deck:user-deck:42:200"),
    ("invalidate_user_ids_by_uuids", "user_uuids", USER_UUID, f"user:id-by-uuid:{USER_UUID}"),
    ("invalidate_card_ids_by_uuids", "card_uuids", CARD_UUID, f"card:id-by-uuid:{CARD_UUID}"),
    ("invalidate_deck_ids_by_uuids", "deck_uuids", DECK_UUID, f"deck:id-by-uuid:{DECK_UUID}"),
])
class TestInvalidateEntries:
    async def test_deletes_requested_cache_key(
        self, cache_service, redis_client, method, argument, identity, key,
    ):
        await getattr(cache_service, method)(**{argument: [identity]})

        redis_client.delete.assert_awaited_once_with(key)

    async def test_does_not_contact_redis_for_empty_input(
        self, cache_service, redis_client, method, argument, identity, key,
    ):
        await getattr(cache_service, method)(**{argument: []})

        assert redis_client.mock_calls == []

    async def test_does_not_fail_when_redis_delete_fails(
        self, cache_service, redis_client, method, argument, identity, key,
    ):
        redis_client.delete.side_effect = ConnectionError("Redis unavailable")

        result = await getattr(cache_service, method)(**{argument: [identity]})

        assert result is None
        redis_client.delete.assert_awaited_once_with(key)

    async def test_propagates_original_redis_error_in_strict_mode(
        self, redis_client, method, argument, identity, key,
    ):
        cache = RedisCacheService(redis=redis_client, raise_errors=True)
        failure = ConnectionError("Redis unavailable")
        redis_client.delete.side_effect = failure

        with pytest.raises(ConnectionError) as error:
            await getattr(cache, method)(**{argument: [identity]})

        assert error.value is failure


@pytest.mark.parametrize(("method", "kind"), [
    ("invalidate_library_card_pages", "cards"),
    ("invalidate_library_deck_pages", "decks"),
])
class TestInvalidateLibraryPages:
    async def test_advances_each_users_generation_with_expiration(
        self, cache_service, redis_client, redis_pipeline, method, kind,
    ):
        await getattr(cache_service, method)(user_ids=[42, 43])

        redis_client.pipeline.assert_called_once_with(transaction=False)
        assert redis_pipeline.method_calls == [
            call.incr(f"library:42:{kind}:generation"),
            call.expire(f"library:42:{kind}:generation", 900),
            call.incr(f"library:43:{kind}:generation"),
            call.expire(f"library:43:{kind}:generation", 900),
            call.execute(),
        ]
        redis_pipeline.execute.assert_awaited_once_with()
        redis_client.delete.assert_not_awaited()

    async def test_does_not_contact_redis_for_empty_input(
        self, cache_service, redis_client, method, kind,
    ):
        await getattr(cache_service, method)(user_ids=[])

        assert redis_client.mock_calls == []

    @pytest.mark.parametrize("failure_stage", ["pipeline", "incr", "expire", "execute"])
    async def test_does_not_fail_when_generation_invalidation_fails(
        self, cache_service, redis_client, redis_pipeline, method, kind, failure_stage,
    ):
        target = redis_client.pipeline if failure_stage == "pipeline" else getattr(
            redis_pipeline, failure_stage,
        )
        target.side_effect = ConnectionError("Redis unavailable")

        result = await getattr(cache_service, method)(user_ids=[42])

        assert result is None

    async def test_propagates_generation_invalidation_error_in_strict_mode(
        self, redis_client, redis_pipeline, method, kind,
    ):
        cache = RedisCacheService(redis=redis_client, raise_errors=True)
        failure = ConnectionError("Redis unavailable")
        redis_pipeline.execute.side_effect = failure

        with pytest.raises(ConnectionError) as error:
            await getattr(cache, method)(user_ids=[42])

        assert error.value is failure


@pytest.fixture
def invalidator_context():
    cache = create_autospec(RedisCacheService, instance=True)
    deck_cards = create_autospec(DeckCardRepository, instance=True)
    user_decks = create_autospec(UserDeckRepository, instance=True)
    deck_cards.get_all_deck_ids_by_card_ids.return_value = []
    user_decks.get_user_ids_by_deck_ids.return_value = []
    return CacheInvalidator(cache, deck_cards, user_decks), cache, deck_cards, user_decks


class TestCacheInvalidatorInvalidate:
    async def test_invalidates_cards_related_decks_and_all_affected_users(
        self, invalidator_context,
    ):
        invalidator, cache, deck_cards, user_decks = invalidator_context
        deck_cards.get_all_deck_ids_by_card_ids.return_value = [200, 201]
        user_decks.get_user_ids_by_deck_ids.return_value = [42, 43]

        await invalidator.invalidate(
            affected_cards=[100, 100], affected_decks=[200], affected_users=[42],
        )

        deck_cards.get_all_deck_ids_by_card_ids.assert_awaited_once_with(card_ids={100})
        user_decks.get_user_ids_by_deck_ids.assert_awaited_once_with(deck_ids={200, 201})
        cache.invalidate_cards.assert_awaited_once_with(card_ids=[100])
        assert set(cache.invalidate_decks.await_args.kwargs["deck_ids"]) == {200, 201}
        assert set(cache.invalidate_deck_cards.await_args.kwargs["deck_ids"]) == {200, 201}
        assert set(cache.invalidate_library_deck_pages.await_args.kwargs["user_ids"]) == {42, 43}
        assert set(cache.invalidate_library_card_pages.await_args.kwargs["user_ids"]) == {42, 43}
        assert set(cache.invalidate_user_decks.await_args.kwargs["identities"]) == {
            (42, 200), (42, 201), (43, 200), (43, 201),
        }

    async def test_resolves_users_for_explicit_decks_without_querying_cards(
        self, invalidator_context,
    ):
        invalidator, cache, deck_cards, user_decks = invalidator_context
        user_decks.get_user_ids_by_deck_ids.return_value = [42]

        await invalidator.invalidate(affected_decks=[200])

        deck_cards.get_all_deck_ids_by_card_ids.assert_not_awaited()
        user_decks.get_user_ids_by_deck_ids.assert_awaited_once_with(deck_ids={200})
        cache.invalidate_decks.assert_awaited_once_with(deck_ids=[200])
        cache.invalidate_user_decks.assert_awaited_once_with(identities=[(42, 200)])

    async def test_invalidates_explicit_users_pages_without_resolving_decks(
        self, invalidator_context,
    ):
        invalidator, cache, deck_cards, user_decks = invalidator_context

        await invalidator.invalidate(affected_users=[42])

        deck_cards.get_all_deck_ids_by_card_ids.assert_not_awaited()
        user_decks.get_user_ids_by_deck_ids.assert_not_awaited()
        cache.invalidate_library_deck_pages.assert_awaited_once_with(user_ids=[42])
        cache.invalidate_library_card_pages.assert_awaited_once_with(user_ids=[42])
        cache.invalidate_user_decks.assert_not_awaited()

    @pytest.mark.parametrize("kwargs", [{}, {
        "affected_cards": [], "affected_decks": [], "affected_users": [],
    }])
    async def test_does_not_resolve_dependencies_without_affected_entities(
        self, invalidator_context, kwargs,
    ):
        invalidator, cache, deck_cards, user_decks = invalidator_context

        await invalidator.invalidate(**kwargs)

        deck_cards.get_all_deck_ids_by_card_ids.assert_not_awaited()
        user_decks.get_user_ids_by_deck_ids.assert_not_awaited()
        cache.invalidate_user_decks.assert_not_awaited()
