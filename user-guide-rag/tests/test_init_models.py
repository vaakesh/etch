from types import SimpleNamespace
from unittest.mock import Mock, call

import httpx
import pytest

import init_models
from rag import dependencies
from rag.config import get_settings


@pytest.fixture
def runtime(dependency_runtime, monkeypatch):
    clock = SimpleNamespace(now=0.0)

    def sleep(seconds):
        clock.now += seconds

    monkeypatch.setattr(init_models.time, "monotonic", lambda: clock.now)
    monkeypatch.setattr(init_models.time, "sleep", Mock(side_effect=sleep))
    dependency_runtime.download = Mock()
    monkeypatch.setattr(init_models, "snapshot_download", dependency_runtime.download)
    dependency_runtime.readiness.get.return_value = httpx.Response(
        200, request=httpx.Request("GET", "http://service/ready")
    )
    return dependency_runtime


class TestWaitForServices:
    def test_downloads_both_models_after_qdrant_is_ready_without_creating_llm_client(
        self, runtime, capsys
    ):
        calls = Mock()
        calls.attach_mock(runtime.readiness.get, "ready")
        calls.attach_mock(runtime.download, "download")

        init_models.main()

        assert calls.mock_calls == [
            call.ready("http://rag-qdrant:6333/readyz", timeout=1.0),
            call.download(repo_id="BAAI/bge-m3"),
            call.download(repo_id="BAAI/bge-reranker-v2-m3"),
        ]
        assert capsys.readouterr().out == (
            "Downloading embedder: BAAI/bge-m3\n"
            "Downloading reranker: BAAI/bge-reranker-v2-m3\nModels are ready.\n"
        )
        runtime.readiness.close.assert_called_once()
        runtime.factories.llm_client.assert_not_called()
        assert dependencies.get_readiness_client.cache_info().currsize == 0
        assert dependencies.get_llm_client.cache_info().currsize == 0

    def test_retries_unavailable_service_at_one_second_intervals(self, runtime):
        ready = runtime.readiness.get.return_value
        runtime.readiness.get.side_effect = [
            httpx.ConnectError("Starting Qdrant"),
            httpx.Response(503, request=httpx.Request("GET", "http://rag-qdrant:6333/readyz")),
            ready,
        ]

        init_models.main()

        assert runtime.readiness.get.call_args_list == [
            call("http://rag-qdrant:6333/readyz", timeout=1.0),
            call("http://rag-qdrant:6333/readyz", timeout=1.0),
            call("http://rag-qdrant:6333/readyz", timeout=1.0),
        ]
        assert init_models.time.sleep.call_args_list == [call(1.0), call(1.0)]
        assert runtime.download.call_args_list == [
            call(repo_id="BAAI/bge-m3"),
            call(repo_id="BAAI/bge-reranker-v2-m3"),
        ]

    def test_aborts_without_downloading_after_readiness_deadline(self, runtime, capsys):
        get_settings().init_timeout = 2.0
        runtime.readiness.get.side_effect = httpx.ConnectError("Still starting")

        with pytest.raises(SystemExit) as exc:
            init_models.main()

        assert exc.value.code == 1
        assert capsys.readouterr().err == (
            "Model initialization failed: Services did not become ready: Qdrant\n"
        )
        runtime.download.assert_not_called()
        runtime.readiness.close.assert_called_once()
        assert dependencies.get_resources.cache_info().currsize == 0
        assert get_settings.cache_info().currsize == 0

    def test_downloads_both_models_from_settings(self, runtime, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "custom/embedding")
        monkeypatch.setenv("RERANKER_MODEL", "custom/reranker")

        init_models.main()

        assert runtime.download.call_args_list == [
            call(repo_id="custom/embedding"),
            call(repo_id="custom/reranker"),
        ]

    @pytest.mark.parametrize(
        ("download_results", "expected_error", "expected_calls"),
        [
            (
                [OSError("Embedder download failed.")],
                "Embedder download failed.",
                [call(repo_id="BAAI/bge-m3")],
            ),
            (
                [None, OSError("Reranker download failed.")],
                "Reranker download failed.",
                [call(repo_id="BAAI/bge-m3"), call(repo_id="BAAI/bge-reranker-v2-m3")],
            ),
        ],
    )
    def test_fails_and_closes_clients_when_model_download_fails(
        self, runtime, capsys, download_results, expected_error, expected_calls
    ):
        runtime.download.side_effect = download_results

        with pytest.raises(SystemExit) as exc:
            init_models.main()

        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert captured.err == f"Model initialization failed: {expected_error}\n"
        assert "Models are ready." not in captured.out
        assert runtime.download.call_args_list == expected_calls
        runtime.factories.llm_client.assert_not_called()
        runtime.readiness.close.assert_called_once()
        assert dependencies.get_resources.cache_info().currsize == 0
        assert get_settings.cache_info().currsize == 0
