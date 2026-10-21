import asyncio
import threading
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import main
from rag import dependencies
from rag.config import PROJECT_DIR, get_settings
from rag.errors import RagError


class TestGetRagService:
    def test_reuses_service_and_clients_with_configured_parameters(self, dependency_runtime):
        runtime = dependency_runtime

        first = dependencies.get_rag_service()
        second = dependencies.get_rag_service()

        assert first is second is runtime.service
        runtime.factories.qdrant.assert_called_once_with(
            url="http://rag-qdrant:6333/",
            grpc_port=6334,
            timeout=10.0,
            check_compatibility=False,
        )
        runtime.factories.llm_client.assert_called_once_with(
            base_url="https://api.openai.com/v1", api_key="test-api-key", timeout=300.0
        )
        runtime.factories.embedder.assert_called_once_with(model_name="BAAI/bge-m3", device="cpu")
        runtime.factories.reranker.assert_called_once_with(
            model_name="BAAI/bge-reranker-v2-m3",
            device="cpu",
            dtype="float32",
            batch_size=8,
            max_length=1024,
        )
        runtime.factories.store.assert_called_once_with(
            client=runtime.qdrant, collection="etch_user_guide_ru"
        )
        runtime.factories.llm.assert_called_once_with(
            client=runtime.llm_client,
            model="gpt-6-luna",
            reasoning_effort="medium",
        )
        runtime.factories.service.assert_called_once_with(
            content_dir=PROJECT_DIR / "content/ru",
            embedder=runtime.factories.embedder.return_value,
            store=runtime.factories.store.return_value,
            llm=runtime.factories.llm.return_value,
            reranker=runtime.factories.reranker.return_value,
            candidate_k=20,
            top_k=5,
        )

    def test_passes_environment_settings_to_the_service(self, dependency_runtime, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "custom/embedding")
        monkeypatch.setenv("QDRANT_COLLECTION", "custom_guide")
        monkeypatch.setenv("TOP_K", "2")
        monkeypatch.setenv("LLM_URL", "https://llm.example/v1")
        monkeypatch.setenv("LLM_API_KEY", "custom-key")
        monkeypatch.setenv("LLM_TIMEOUT", "30")
        monkeypatch.setenv("LLM_MODEL", "custom-model")
        monkeypatch.setenv("LLM_REASONING_EFFORT", "high")

        dependencies.get_rag_service()

        dependency_runtime.factories.embedder.assert_called_once_with(
            model_name="custom/embedding", device="cpu"
        )
        dependency_runtime.factories.store.assert_called_once_with(
            client=dependency_runtime.qdrant, collection="custom_guide"
        )
        assert dependency_runtime.factories.service.call_args.kwargs["top_k"] == 2
        dependency_runtime.factories.llm_client.assert_called_once_with(
            base_url="https://llm.example/v1", api_key="custom-key", timeout=30.0
        )
        dependency_runtime.factories.llm.assert_called_once_with(
            client=dependency_runtime.llm_client, model="custom-model", reasoning_effort="high"
        )


class TestGetAskLock:
    def test_reuses_one_lock_until_caches_are_cleared(self, cached_dependencies):
        first = dependencies.get_ask_lock()

        assert dependencies.get_ask_lock() is first
        dependencies.clear_dependency_caches()
        assert dependencies.get_ask_lock() is not first


class TestLifespan:
    def test_indexes_before_serving_reuses_dependencies_and_closes_clients(
        self, dependency_runtime
    ):
        runtime = dependency_runtime

        with TestClient(main.app) as client:
            runtime.service.index.assert_called_once_with()
            first = client.post("/ask", json={"message": "Первый вопрос"})
            second = client.post("/ask", json={"message": "Второй вопрос"})
            runtime.qdrant.close.assert_not_called()
            runtime.llm_client.close.assert_not_called()
            assert isinstance(dependencies.get_ask_lock(), asyncio.Lock)

        assert first.status_code == 200
        assert second.status_code == 200
        runtime.factories.service.assert_called_once()
        runtime.qdrant.close.assert_called_once()
        runtime.llm_client.close.assert_called_once()
        assert dependencies.get_rag_service.cache_info().currsize == 0
        assert dependencies.get_ask_lock.cache_info().currsize == 0

    @pytest.mark.anyio
    async def test_waits_for_index_in_worker_before_finishing_startup(self, dependency_runtime):
        started = asyncio.Event()
        release = threading.Event()
        loop = asyncio.get_running_loop()
        event_loop_thread = threading.get_ident()
        index_threads = []

        def index():
            index_threads.append(threading.get_ident())
            loop.call_soon_threadsafe(started.set)
            if not release.wait(timeout=5):
                raise TimeoutError("Indexing was not released.")
            return 45

        dependency_runtime.service.index.side_effect = index
        lifespan = main.lifespan(main.app)
        startup = asyncio.create_task(lifespan.__aenter__())
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            assert not startup.done()
            assert index_threads[0] != event_loop_thread
        finally:
            release.set()
            await startup
            await lifespan.__aexit__(None, None, None)

    def test_indexes_again_with_fresh_dependencies_after_restart(self, dependency_runtime):
        with TestClient(main.app):
            first_lock = dependencies.get_ask_lock()
        with TestClient(main.app):
            second_lock = dependencies.get_ask_lock()

        assert first_lock is not second_lock
        assert dependency_runtime.service.index.call_count == 2
        assert dependency_runtime.factories.service.call_count == 2
        assert dependency_runtime.qdrant.close.call_count == 2
        assert dependency_runtime.llm_client.close.call_count == 2

    def test_closes_qdrant_when_llm_client_creation_fails(self, dependency_runtime):
        runtime = dependency_runtime
        runtime.factories.llm_client.side_effect = ValueError("Invalid LLM URL.")

        with pytest.raises(ValueError, match="Invalid LLM URL"):
            with TestClient(main.app):
                pytest.fail("Startup must fail before accepting requests.")

        runtime.qdrant.close.assert_called_once()
        runtime.llm_client.close.assert_not_called()
        assert dependencies.get_qdrant_client.cache_info().currsize == 0
        assert dependencies.get_resources.cache_info().currsize == 0

    @pytest.mark.parametrize("factory", ["embedder", "reranker", "service"])
    def test_closes_clients_when_service_construction_fails(self, dependency_runtime, factory):
        runtime = dependency_runtime
        getattr(runtime.factories, factory).side_effect = RagError("Initialization failed.")

        with pytest.raises(RagError, match="Initialization failed"):
            with TestClient(main.app):
                pytest.fail("Startup must fail before accepting requests.")

        runtime.qdrant.close.assert_called_once()
        runtime.llm_client.close.assert_called_once()
        assert dependencies.get_rag_service.cache_info().currsize == 0
        assert get_settings.cache_info().currsize == 0

    def test_aborts_startup_and_closes_clients_when_index_fails(self, dependency_runtime):
        runtime = dependency_runtime
        runtime.service.index.side_effect = RagError("Indexing failed.")

        with pytest.raises(RagError, match="Indexing failed"):
            with TestClient(main.app):
                pytest.fail("Startup must fail before accepting requests.")

        runtime.service.ask.assert_not_called()
        runtime.qdrant.close.assert_called_once()
        runtime.llm_client.close.assert_called_once()
        assert dependencies.get_rag_service.cache_info().currsize == 0
        assert dependencies.get_ask_lock.cache_info().currsize == 0

    @pytest.mark.parametrize("failing_client", ["llm_client", "qdrant"])
    def test_closes_all_clients_and_clears_caches_even_when_close_fails(
        self, dependency_runtime, failing_client, monkeypatch
    ):
        runtime = dependency_runtime
        getattr(runtime, failing_client).close.side_effect = RuntimeError("Close failed.")
        cleanup = Mock()
        cleanup.attach_mock(runtime.llm_client.close, "llm_client")
        cleanup.attach_mock(runtime.qdrant.close, "qdrant")
        cleanup.attach_mock(Mock(wraps=dependencies.clear_dependency_caches), "clear")
        monkeypatch.setattr(main, "clear_dependency_caches", cleanup.clear)

        with pytest.raises(RuntimeError, match="Close failed"):
            with TestClient(main.app):
                pass

        assert [entry[0] for entry in cleanup.mock_calls] == ["llm_client", "qdrant", "clear"]
        runtime.llm_client.close.assert_called_once()
        runtime.qdrant.close.assert_called_once()
        assert dependencies.get_rag_service.cache_info().currsize == 0
        assert dependencies.get_qdrant_client.cache_info().currsize == 0
        assert dependencies.get_llm_client.cache_info().currsize == 0
        assert dependencies.get_ask_lock.cache_info().currsize == 0
        assert get_settings.cache_info().currsize == 0
        assert dependencies.get_resources.cache_info().currsize == 0
