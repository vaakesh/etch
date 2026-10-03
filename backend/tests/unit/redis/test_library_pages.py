from types import SimpleNamespace
from unittest.mock import call

import orjson
import pytest
from redis.exceptions import ConnectionError, TimeoutError


@pytest.fixture(params=[
    ("cards", "card_ids", "37a3904a92f6fa4b85758908843551a645f279fcbe58c22114a3b5892613aaab",
     "5106a5b904ecc08e5531f978f8f86e2670cd65bfb2d7c47590ae9e3ee2e3f9e5"),
    ("decks", "deck_ids", "6f00dabbf6e22ffe929ee2518be0ed997fb8f903b5b83446acee479e0c08a3dc",
     "5450a08662f7ea61f6916e4866009f7f32d7f0e1cdce25f9fb3403789f1dbf50"),
], ids=["cards", "decks"])
def page_case(request):
    kind, ids_argument, fingerprint, filtered_fingerprint = request.param
    return SimpleNamespace(
        kind=kind,
        ids_argument=ids_argument,
        cache_method=f"cache_library_{kind}_page",
        get_method=f"get_cached_library_{kind}_page",
        generation_key=f"library:42:{kind}:generation",
        page_key=f"library:42:{kind}:v3:{fingerprint}",
        first_page_key=f"library:42:{kind}:v0:{fingerprint}",
        filtered_page_key=f"library:42:{kind}:v3:{filtered_fingerprint}",
    )


class TestCacheLibraryPages:
    async def test_stores_page_ids_and_pagination_with_expected_generation(
        self, cache_service, redis_client, page_case,
    ):
        kwargs = {
            "user_id": 42, page_case.ids_argument: [100, 101],
            "expected_generation": 3, "next_cursor": "next", "has_more": True,
        }

        await getattr(cache_service, page_case.cache_method)(**kwargs)

        write = redis_client.set.await_args.kwargs
        assert write["name"] == page_case.page_key
        assert write["ex"] == 317
        assert orjson.loads(write["value"]) == {
            "items": [100, 101], "next_cursor": "next", "has_more": True,
        }
        redis_client.set.assert_awaited_once()
        redis_client.get.assert_not_awaited()

    async def test_caches_empty_page(self, cache_service, redis_client, page_case):
        kwargs = {
            "user_id": 42, page_case.ids_argument: [],
            "expected_generation": 3, "next_cursor": None, "has_more": False,
        }

        await getattr(cache_service, page_case.cache_method)(**kwargs)

        write = redis_client.set.await_args.kwargs
        assert write["name"] == page_case.page_key
        assert orjson.loads(write["value"]) == {
            "items": [], "next_cursor": None, "has_more": False,
        }

    async def test_skips_write_without_valid_generation(
        self, cache_service, redis_client, page_case,
    ):
        kwargs = {
            "user_id": 42, page_case.ids_argument: [100],
            "expected_generation": None, "next_cursor": None, "has_more": False,
        }

        await getattr(cache_service, page_case.cache_method)(**kwargs)

        assert redis_client.mock_calls == []

    async def test_preserves_query_cursor_limit_and_favourite_filter_in_cache_key(
        self, cache_service, redis_client, page_case,
    ):
        kwargs = {
            "user_id": 42, page_case.ids_argument: [100],
            "expected_generation": 3, "next_cursor": None, "has_more": False,
            "search_query": "hello", "cursor": "cursor", "limit": 25,
        }
        if page_case.kind == "decks":
            kwargs["is_favourite"] = True

        await getattr(cache_service, page_case.cache_method)(**kwargs)

        assert redis_client.set.await_args.kwargs["name"] == page_case.filtered_page_key

    async def test_does_not_fail_when_page_write_fails(
        self, cache_service, redis_client, page_case,
    ):
        redis_client.set.side_effect = ConnectionError("Redis unavailable")
        kwargs = {
            "user_id": 42, page_case.ids_argument: [100],
            "expected_generation": 3, "next_cursor": None, "has_more": False,
        }

        result = await getattr(cache_service, page_case.cache_method)(**kwargs)

        assert result is None
        redis_client.set.assert_awaited_once()


class TestGetCachedLibraryPages:
    @pytest.mark.parametrize("as_bytes", [False, True], ids=["string", "bytes"])
    async def test_returns_page_and_generation(
        self, cache_service, redis_client, page_case, as_bytes,
    ):
        payload = b'{"items":[100,101],"next_cursor":"next","has_more":true}'
        redis_client.get.side_effect = ["3", payload if as_bytes else payload.decode()]

        result = await getattr(cache_service, page_case.get_method)(user_id=42)

        assert result.generation == 3
        assert result.page.model_dump() == {
            "items": [100, 101], "next_cursor": "next", "has_more": True,
        }
        assert redis_client.get.await_args_list == [
            call(page_case.generation_key), call(page_case.page_key),
        ]
        redis_client.delete.assert_not_awaited()

    async def test_uses_generation_zero_when_counter_is_absent(
        self, cache_service, redis_client, page_case,
    ):
        redis_client.get.side_effect = [None, None]

        result = await getattr(cache_service, page_case.get_method)(user_id=42)

        assert result.page is None
        assert result.generation == 0
        assert redis_client.get.await_args_list == [
            call(page_case.generation_key), call(page_case.first_page_key),
        ]

    async def test_retains_generation_when_page_is_absent(
        self, cache_service, redis_client, page_case,
    ):
        redis_client.get.side_effect = ["3", None]

        result = await getattr(cache_service, page_case.get_method)(user_id=42)

        assert result.page is None
        assert result.generation == 3
        redis_client.delete.assert_not_awaited()

    async def test_reads_page_for_requested_filters(
        self, cache_service, redis_client, page_case,
    ):
        redis_client.get.side_effect = ["3", None]
        kwargs = {"user_id": 42, "search_query": "hello", "cursor": "cursor", "limit": 25}
        if page_case.kind == "decks":
            kwargs["is_favourite"] = True

        result = await getattr(cache_service, page_case.get_method)(**kwargs)

        assert result.page is None
        assert result.generation == 3
        assert redis_client.get.await_args_list == [
            call(page_case.generation_key), call(page_case.filtered_page_key),
        ]

    @pytest.mark.parametrize("generation", ["not-an-int", "1.5", "-1"])
    async def test_skips_page_read_for_invalid_generation(
        self, cache_service, redis_client, page_case, generation,
    ):
        redis_client.get.return_value = generation

        result = await getattr(cache_service, page_case.get_method)(user_id=42)

        assert result.page is None
        assert result.generation is None
        redis_client.get.assert_awaited_once_with(page_case.generation_key)

    async def test_disables_page_caching_when_generation_read_fails(
        self, cache_service, redis_client, page_case,
    ):
        redis_client.get.side_effect = ConnectionError("Redis unavailable")

        result = await getattr(cache_service, page_case.get_method)(user_id=42)

        assert result.page is None
        assert result.generation is None
        redis_client.get.assert_awaited_once_with(page_case.generation_key)

    async def test_returns_miss_when_page_read_fails(
        self, cache_service, redis_client, page_case,
    ):
        redis_client.get.side_effect = ["3", TimeoutError("Redis unavailable")]

        result = await getattr(cache_service, page_case.get_method)(user_id=42)

        assert result.page is None
        assert result.generation == 3

    @pytest.mark.parametrize("value", [
        "not-json", "[]", '{"items":["not-an-id"],"next_cursor":null,"has_more":false}',
    ])
    @pytest.mark.parametrize("delete_fails", [False, True])
    async def test_returns_miss_for_corrupted_page_even_when_cleanup_fails(
        self, cache_service, redis_client, page_case, value, delete_fails,
    ):
        redis_client.get.side_effect = ["3", value]
        if delete_fails:
            redis_client.delete.side_effect = TimeoutError("Redis unavailable")

        result = await getattr(cache_service, page_case.get_method)(user_id=42)

        assert result.page is None
        assert result.generation == 3
        redis_client.delete.assert_awaited_once_with(page_case.page_key)
