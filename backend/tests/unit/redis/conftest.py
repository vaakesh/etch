from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.asyncio import Redis
from redis.asyncio.client import Pipeline

from app.redis.service import RedisCacheService


@pytest.fixture
def redis_pipeline():
    pipeline = MagicMock(spec_set=Pipeline)
    pipeline.execute = AsyncMock(return_value=[])
    return pipeline


@pytest.fixture
def redis_client(redis_pipeline):
    redis = MagicMock(spec_set=Redis)
    redis.pipeline.return_value = redis_pipeline
    redis.get = AsyncMock(return_value=None)
    redis.mget = AsyncMock(return_value=[])
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.eval = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def cache_service(redis_client, monkeypatch):
    monkeypatch.setattr("app.redis.service.random.randint", lambda start, end: 17)
    return RedisCacheService(redis=redis_client)
