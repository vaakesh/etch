from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec

import pytest
from fastapi import Request, status
from httpx import AsyncClient

from app.redis.deps import limit
from app.redis.errors import RateLimitError
from app.redis.service import RateLimit, RateLimitPolicy, RedisRateLimiter


class TestRedisRateLimiterCheck:
    async def test_initializes_counter_and_allows_first_request(self):
        redis = AsyncMock()
        redis.get.return_value = None
        rate_limiter = RedisRateLimiter(redis=redis)

        allowed = await rate_limiter.check(
            redis_key="rate_limit:user:42:cards",
            requests=10,
            window_seconds=60,
        )

        assert allowed is True
        redis.get.assert_awaited_once_with(
            name="rate_limit:user:42:cards",
        )
        redis.set.assert_awaited_once_with(
            name="rate_limit:user:42:cards",
            value="1",
            ex=60,
        )
        redis.incrby.assert_not_awaited()

    async def test_allows_request_at_limit_boundary(self):
        redis = AsyncMock()
        redis.get.return_value = "4"
        redis.incrby.return_value = 5
        rate_limiter = RedisRateLimiter(redis=redis)

        allowed = await rate_limiter.check(
            redis_key="rate_limit:user:42:cards",
            requests=5,
            window_seconds=60,
        )

        assert allowed is True
        redis.incrby.assert_awaited_once_with(
            name="rate_limit:user:42:cards",
            amount=1,
        )
        redis.set.assert_not_awaited()

    async def test_rejects_request_over_limit(self):
        redis = AsyncMock()
        redis.get.return_value = "5"
        redis.incrby.return_value = 6
        rate_limiter = RedisRateLimiter(redis=redis)

        allowed = await rate_limiter.check(
            redis_key="rate_limit:user:42:cards",
            requests=5,
            window_seconds=60,
        )

        assert allowed is False


class TestRateLimit:
    async def test_checks_expected_identity_key(self):
        rate_limiter = create_autospec(RedisRateLimiter, instance=True)
        rate_limiter.check.return_value = True
        policy = RateLimitPolicy(
            route="cards",
            requests=10,
            window_seconds=60,
        )
        rate_limit = RateLimit(
            policy=policy,
            rate_limiter=rate_limiter,
            by_identity="user",
            identity_key="42",
        )

        await rate_limit()

        rate_limiter.check.assert_awaited_once_with(
            redis_key="rate_limit:user:42:cards",
            requests=10,
            window_seconds=60,
        )

    async def test_raises_rate_limit_error_when_request_is_rejected(self):
        rate_limiter = create_autospec(RedisRateLimiter, instance=True)
        rate_limiter.check.return_value = False
        policy = RateLimitPolicy(
            route="cards",
            requests=10,
            window_seconds=60,
        )
        rate_limit = RateLimit(
            policy=policy,
            rate_limiter=rate_limiter,
            by_identity="user",
            identity_key="42",
        )

        with pytest.raises(
            RateLimitError,
            match="Too many requests. Please try again later.",
        ):
            await rate_limit()


class TestRateLimitDependency:
    async def test_uses_current_user_id_for_user_identity(self):
        rate_limiter = create_autospec(RedisRateLimiter, instance=True)
        rate_limiter.check.return_value = True
        policy = RateLimitPolicy(
            route="cards",
            requests=10,
            window_seconds=60,
        )
        dependency = limit(policy=policy, by_identity="user")
        user = SimpleNamespace(id=42)

        await dependency(
            user=user,
            rate_limiter=rate_limiter,
        )

        rate_limiter.check.assert_awaited_once_with(
            redis_key="rate_limit:user:42:cards",
            requests=10,
            window_seconds=60,
        )

    @pytest.mark.parametrize(
        ("client", "expected_identity"),
        [
            pytest.param(("203.0.113.10", 1234), "203.0.113.10", id="client_ip"),
            pytest.param(("", 1234), "unknown", id="unknown_ip"),
        ],
    )
    async def test_uses_client_ip_or_unknown_for_ip_identity(
        self,
        client,
        expected_identity,
    ):
        rate_limiter = create_autospec(RedisRateLimiter, instance=True)
        rate_limiter.check.return_value = True
        policy = RateLimitPolicy(
            route="login",
            requests=10,
            window_seconds=60,
        )
        dependency = limit(policy=policy, by_identity="ip")
        request = Request({"type": "http", "client": client})

        await dependency(
            request=request,
            rate_limiter=rate_limiter,
        )

        rate_limiter.check.assert_awaited_once_with(
            redis_key=f"rate_limit:ip:{expected_identity}:login",
            requests=10,
            window_seconds=60,
        )


class TestRateLimitResponse:
    async def test_returns_429_when_route_limit_is_exceeded(
        self,
        client: AsyncClient,
        current_user,
        redis_rate_limiter: AsyncMock,
        user_service: AsyncMock,
    ):
        redis_rate_limiter.check.return_value = False

        response = await client.get("/users/me")

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.json() == {
            "message": "Too many requests. Please try again later.",
        }
        redis_rate_limiter.check.assert_awaited_once_with(
            redis_key=f"rate_limit:user:{current_user.id}:profile",
            requests=60,
            window_seconds=60,
        )
        user_service.get_user_settings_by_id.assert_not_awaited()
