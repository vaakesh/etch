import logging
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from fastapi import Request, status
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from app.redis.errors import RateLimitError
from app.redis.rate_limiters import limit
from app.redis.service import RATE_LIMIT_SCRIPT, RateLimit, RateLimitPolicy, RedisRateLimiter


@pytest.fixture
def limiter():
    return create_autospec(RedisRateLimiter, instance=True)


@pytest.fixture
def policy():
    return RateLimitPolicy(route="cards", requests=5, window_seconds=60)


class TestRedisRateLimiterCheck:
    @pytest.mark.parametrize(("counter", "expected"), [
        pytest.param(1, True, id="first_request"),
        pytest.param(5, True, id="at_limit"),
        pytest.param(6, False, id="over_limit"),
    ])
    async def test_compares_atomic_counter_with_limit(self, redis_client, counter, expected):
        redis_client.eval.return_value = counter
        rate_limiter = RedisRateLimiter(redis=redis_client)

        result = await rate_limiter.check(
            redis_key="rate_limit:user:42:cards", requests=5, window_seconds=60,
        )

        assert result is expected
        redis_client.eval.assert_awaited_once_with(
            RATE_LIMIT_SCRIPT, 1, "rate_limit:user:42:cards", 60,
        )
        redis_client.get.assert_not_awaited()
        redis_client.set.assert_not_awaited()

    @pytest.mark.parametrize("error_type", [RedisError, ConnectionError, TimeoutError])
    async def test_returns_unavailable_result_and_logs_redis_error(
        self, redis_client, error_type, caplog,
    ):
        redis_client.eval.side_effect = error_type("Redis unavailable")
        rate_limiter = RedisRateLimiter(redis=redis_client)

        with caplog.at_level(logging.WARNING, logger="app.redis.service"):
            result = await rate_limiter.check(
                redis_key="rate_limit:user:42:cards", requests=5, window_seconds=60,
            )

        assert result is None
        assert len(caplog.records) == 1
        assert caplog.records[0].cache_operation == "check rate limit"
        assert caplog.records[0].exc_info[0] is error_type

    async def test_propagates_unexpected_error(self, redis_client):
        redis_client.eval.side_effect = RuntimeError("Unexpected failure")
        rate_limiter = RedisRateLimiter(redis=redis_client)

        with pytest.raises(RuntimeError, match="Unexpected failure"):
            await rate_limiter.check(
                redis_key="rate_limit:user:42:cards", requests=5, window_seconds=60,
            )


class TestRateLimitCall:
    @pytest.mark.parametrize("allowed", [True, None], ids=["allowed", "redis_unavailable"])
    @pytest.mark.parametrize(("identity", "key", "expected_key"), [
        ("user", 42, "rate_limit:user:42:cards"),
        ("ip", "203.0.113.10", "rate_limit:ip:203.0.113.10:cards"),
    ])
    async def test_allows_request_when_limit_is_not_rejected(
        self, limiter, policy, allowed, identity, key, expected_key,
    ):
        limiter.check.return_value = allowed
        rate_limit = RateLimit(policy, limiter, by_identity=identity, identity_key=key)

        result = await rate_limit()

        assert result is None
        limiter.check.assert_awaited_once_with(
            redis_key=expected_key, requests=5, window_seconds=60,
        )

    async def test_raises_rate_limit_error_when_request_is_rejected(self, limiter, policy):
        limiter.check.return_value = False
        rate_limit = RateLimit(policy, limiter, by_identity="user", identity_key=42)

        with pytest.raises(RateLimitError) as error:
            await rate_limit()

        assert str(error.value) == "Too many requests. Please try again later."
        limiter.check.assert_awaited_once_with(
            redis_key="rate_limit:user:42:cards", requests=5, window_seconds=60,
        )


class TestLimitDependency:
    async def test_uses_current_user_id_for_user_identity(self, limiter, policy):
        limiter.check.return_value = True
        dependency = limit(policy=policy, by_identity="user")

        await dependency(user=SimpleNamespace(id=42), rate_limiter=limiter)

        limiter.check.assert_awaited_once_with(
            redis_key="rate_limit:user:42:cards", requests=5, window_seconds=60,
        )

    @pytest.mark.parametrize(("client_address", "expected_key"), [
        (("203.0.113.10", 1234), "rate_limit:ip:203.0.113.10:cards"),
        (("2001:db8::1", 1234), "rate_limit:ip:2001:db8::1:cards"),
        (("", 1234), "rate_limit:ip:unknown:cards"),
        (None, "rate_limit:ip:unknown:cards"),
    ])
    async def test_uses_client_host_or_unknown_for_ip_identity(
        self, limiter, policy, client_address, expected_key,
    ):
        limiter.check.return_value = True
        dependency = limit(policy=policy, by_identity="ip")
        request = Request({
            "type": "http", "client": client_address,
            "headers": [(b"x-forwarded-for", b"198.51.100.20")],
        })

        await dependency(request=request, rate_limiter=limiter)

        limiter.check.assert_awaited_once_with(
            redis_key=expected_key, requests=5, window_seconds=60,
        )

    @pytest.mark.parametrize("identity", ["session", "", None])
    def test_rejects_unsupported_identity(self, policy, identity):
        with pytest.raises(ValueError, match=f"{identity} identity not found"):
            limit(policy=policy, by_identity=identity)

    @pytest.mark.parametrize("identity", ["user", "ip"])
    async def test_propagates_limit_rejection(self, limiter, policy, identity):
        limiter.check.return_value = False
        dependency = limit(policy=policy, by_identity=identity)
        kwargs = {"user": SimpleNamespace(id=42)} if identity == "user" else {
            "request": Request({"type": "http", "client": ("203.0.113.10", 1234)}),
        }

        with pytest.raises(RateLimitError):
            await dependency(rate_limiter=limiter, **kwargs)

        limiter.check.assert_awaited_once()


class TestRateLimitResponse:
    @pytest.mark.parametrize(
        ("method", "path", "payload", "expected_key", "requests", "window"),
        [
            ("GET", "/users/me", None, "rate_limit:user:42:profile", 60, 60),
            ("POST", "/cards/", {"front_text": "привет", "back_text": "hello"},
             "rate_limit:user:42:cards", 120, 60),
            ("GET", "/decks/0198ad01-b200-7000-8000-000000000200", None,
             "rate_limit:ip:127.0.0.1:decks:public", 180, 60),
            ("POST", "/decks/0198ad01-b200-7000-8000-000000000200/cards/import",
             {"cards": [{"front_text": "привет", "back_text": "hello"}]},
             "rate_limit:user:42:decks:import", 20, 60),
        ],
        ids=["profile", "cards", "public_decks", "deck_import"],
    )
    async def test_returns_429_before_calling_business_services(
        self, client, redis_rate_limiter, user_service, card_service, deck_service,
        method, path, payload, expected_key, requests, window,
    ):
        redis_rate_limiter.check.return_value = False

        response = await client.request(method, path, json=payload)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.json() == {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
        }
        redis_rate_limiter.check.assert_awaited_once_with(
            redis_key=expected_key, requests=requests, window_seconds=window,
        )
        assert user_service.mock_calls == []
        assert card_service.mock_calls == []
        assert deck_service.mock_calls == []

    async def test_returns_normal_response_when_redis_is_unavailable(
        self, client, redis_rate_limiter,
    ):
        redis_rate_limiter.check.return_value = None

        response = await client.get("/users/me")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "test-user",
            "email": "test@example.com",
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "ru-RU", "theme": "system", "show_previews_for_long": True,
            },
        }
        redis_rate_limiter.check.assert_awaited_once_with(
            redis_key="rate_limit:user:42:profile", requests=60, window_seconds=60,
        )
