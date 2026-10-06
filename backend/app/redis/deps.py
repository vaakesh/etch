
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from functools import lru_cache

from app.config import get_settings
from app.tracing import traced
from app.redis.service import (
    RedisCacheService,
    RedisRateLimiter,
)

@lru_cache
@traced("redis.deps.get_redis")
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
