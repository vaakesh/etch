from functools import lru_cache
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, create_autospec

import httpx
import pytest
from redis.asyncio import Redis

from app import main
from app.deps import get_resources
from app.rag import deps as rag_deps


@pytest.fixture
async def lifespan_runtime(monkeypatch):
    await get_resources().aclose()
    get_resources.cache_clear()
    rag_deps.get_rag_client.cache_clear()
    redis = create_autospec(Redis, instance=True)
    redis.ping = AsyncMock(return_value=True)
    http = create_autospec(httpx.AsyncClient, instance=True)
    http_factory = Mock(return_value=http)
    trace_provider = SimpleNamespace(resource=object())
    log_provider = object()
    log_handler = object()
    shutdown_tracing = Mock()
    shutdown_logging = Mock()

    @lru_cache(maxsize=1)
    def redis_factory():
        return redis

    monkeypatch.setattr(main, "setup_logging", Mock())
    monkeypatch.setattr(main, "setup_tracing", Mock(return_value=trace_provider))
    monkeypatch.setattr(
        main, "setup_otel_logging", Mock(return_value=(log_provider, log_handler)),
    )
    monkeypatch.setattr(main, "shutdown_tracing", shutdown_tracing)
    monkeypatch.setattr(main, "shutdown_otel_logging", shutdown_logging)
    monkeypatch.setattr(main, "get_redis", redis_factory)
    monkeypatch.setattr(rag_deps.httpx, "AsyncClient", http_factory)
    monkeypatch.setattr(
        rag_deps, "get_settings",
        lambda: SimpleNamespace(
            rag_base_url="http://rag-service:8000", rag_request_timeout=60,
        ),
    )

    try:
        yield SimpleNamespace(
            redis=redis,
            redis_factory=redis_factory,
            http=http,
            http_factory=http_factory,
            trace_provider=trace_provider,
            log_provider=log_provider,
            log_handler=log_handler,
            shutdown_tracing=shutdown_tracing,
            shutdown_logging=shutdown_logging,
            closers={
                "http": http.aclose,
                "redis": redis.aclose,
                "tracing": shutdown_tracing,
                "logging": shutdown_logging,
            },
        )
    finally:
        await get_resources().aclose()
        rag_deps.get_rag_client.cache_clear()
        get_resources.cache_clear()


class TestLifespan:
    async def test_reuses_rag_dependency_and_closes_resources_on_shutdown(
        self, lifespan_runtime,
    ):
        runtime = lifespan_runtime

        async with main.lifespan(main.app):
            first = rag_deps.get_rag_client()
            second = rag_deps.get_rag_client()
            runtime.http.aclose.assert_not_awaited()
            runtime.redis.aclose.assert_not_awaited()

        assert first is second
        runtime.http_factory.assert_called_once()
        runtime.http.post.assert_not_awaited()
        runtime.redis.ping.assert_awaited_once()
        runtime.http.aclose.assert_awaited_once()
        runtime.redis.aclose.assert_awaited_once()
        runtime.shutdown_tracing.assert_called_once_with(runtime.trace_provider)
        runtime.shutdown_logging.assert_called_once_with(
            runtime.log_provider, runtime.log_handler,
        )
        assert rag_deps.get_rag_client.cache_info().currsize == 0
        assert runtime.redis_factory.cache_info().currsize == 0
        assert get_resources.cache_info().currsize == 0

    async def test_closes_created_resources_when_redis_startup_fails(
        self, lifespan_runtime,
    ):
        runtime = lifespan_runtime
        runtime.redis.ping.side_effect = RuntimeError("Redis startup failed")

        with pytest.raises(RuntimeError, match="Redis startup failed"):
            async with main.lifespan(main.app):
                pytest.fail("Startup must fail before serving requests")

        runtime.http.aclose.assert_awaited_once()
        runtime.redis.aclose.assert_awaited_once()
        runtime.shutdown_tracing.assert_called_once()
        runtime.shutdown_logging.assert_called_once()
        assert rag_deps.get_rag_client.cache_info().currsize == 0
        assert runtime.redis_factory.cache_info().currsize == 0
        assert get_resources.cache_info().currsize == 0

    async def test_closes_http_when_rag_client_construction_fails(
        self, lifespan_runtime, monkeypatch,
    ):
        runtime = lifespan_runtime
        monkeypatch.setattr(
            rag_deps, "RagClient", Mock(side_effect=ValueError("Invalid RAG client")),
        )

        with pytest.raises(ValueError, match="Invalid RAG client"):
            async with main.lifespan(main.app):
                pytest.fail("Startup must fail before serving requests")

        runtime.http.aclose.assert_awaited_once()
        runtime.redis.aclose.assert_awaited_once()
        runtime.shutdown_tracing.assert_called_once()
        runtime.shutdown_logging.assert_called_once()
        assert rag_deps.get_rag_client.cache_info().currsize == 0
        assert get_resources.cache_info().currsize == 0

    async def test_shuts_down_tracing_when_logging_setup_fails(
        self, lifespan_runtime, monkeypatch,
    ):
        runtime = lifespan_runtime
        monkeypatch.setattr(
            main, "setup_otel_logging", Mock(side_effect=RuntimeError("Logging failed")),
        )

        with pytest.raises(RuntimeError, match="Logging failed"):
            async with main.lifespan(main.app):
                pytest.fail("Startup must fail before serving requests")

        runtime.shutdown_tracing.assert_called_once_with(runtime.trace_provider)
        runtime.shutdown_logging.assert_not_called()
        runtime.http_factory.assert_not_called()
        assert get_resources.cache_info().currsize == 0

    @pytest.mark.parametrize("failing_close", ["http", "redis", "tracing", "logging"])
    async def test_attempts_all_cleanup_and_clears_caches_when_a_close_fails(
        self, lifespan_runtime, failing_close,
    ):
        runtime = lifespan_runtime
        runtime.closers[failing_close].side_effect = RuntimeError("Close failed")

        with pytest.raises(RuntimeError, match="Close failed"):
            async with main.lifespan(main.app):
                pass

        runtime.http.aclose.assert_awaited_once()
        runtime.redis.aclose.assert_awaited_once()
        runtime.shutdown_tracing.assert_called_once()
        runtime.shutdown_logging.assert_called_once()
        assert rag_deps.get_rag_client.cache_info().currsize == 0
        assert runtime.redis_factory.cache_info().currsize == 0
        assert get_resources.cache_info().currsize == 0

    async def test_creates_fresh_rag_client_after_lifespan_restarts(
        self, lifespan_runtime,
    ):
        runtime = lifespan_runtime

        async with main.lifespan(main.app):
            first = rag_deps.get_rag_client()
        async with main.lifespan(main.app):
            second = rag_deps.get_rag_client()

        assert first is not second
        assert runtime.http_factory.call_count == 2
        assert runtime.http.aclose.await_count == 2
        assert runtime.redis.aclose.await_count == 2
