
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from functools import lru_cache

from app.config import get_settings

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

RedisDep = Annotated[
    Redis,
    Depends(get_redis),
]