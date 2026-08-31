
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from functools import lru_cache

from app.config import get_settings
from app.redis.service import (
    RateLimit,
    RateLimitIdentity,
    RateLimitPolicy,
    RedisCacheService,
    RedisRateLimiter,
)
from app.auth.deps import CurrentUser

@lru_cache
def get_redis() -> Redis:
    settings = get_settings()

    redis = Redis.from_url(
        url=settings.redis_url(),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        max_connections=20,
    )
    return redis

def get_redis_service(
    redis: Redis = Depends(get_redis),
):
    return RedisCacheService(redis=redis)

def get_redis_rate_limiter(
    redis: Redis = Depends(get_redis),
):
    return RedisRateLimiter(
        redis=redis,
    )

type RedisRateLimiterDeps = Annotated[
    RedisRateLimiter,
    Depends(get_redis_rate_limiter),
]

type CacheServiceDeps = Annotated[
    RedisCacheService,
    Depends(get_redis_service),
]

def limit(
    policy: RateLimitPolicy,
    by_identity: RateLimitIdentity,
):
    if by_identity == "user":
        async def user_dependency(
            user: CurrentUser,
            rate_limiter: RedisRateLimiterDeps,
        ):
            limiter = RateLimit(
                policy=policy,
                rate_limiter=rate_limiter,
                by_identity=by_identity,
                identity_key=user.id,
            )
            await limiter()

        return user_dependency

    if by_identity == "ip":
        async def ip_dependency(
            request: Request,
            rate_limiter: RedisRateLimiterDeps,
        ):
            host = (
                request.client.host
                if request.client and request.client.host
                else "unknown"
            ) 
            limiter = RateLimit(
                policy=policy,
                rate_limiter=rate_limiter,
                by_identity=by_identity,
                identity_key=host,
            )
            await limiter()

        return ip_dependency

    raise ValueError(f"{by_identity} identity not found")
