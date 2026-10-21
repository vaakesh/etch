from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rag import dependencies
from rag.config import PROJECT_DIR, Settings
from rag.embedder import Embedder
from rag.llm import LLM
from rag.reranker import Reranker
from rag.service import RagService
from rag.store import QdrantStore
from rag.types import Answer, Chunk, RerankedHit, SearchHit


@pytest.fixture
def chunk():
    return Chunk(
        chunk_id="etch.cards.create",
        title="Etch: как создать карточку",
        text="# Etch: как создать карточку\n\nНажмите «Новая карточка».",
        source="content/ru/05-cards.md",
    )


@pytest.fixture
def hit():
    return SearchHit(
        chunk_id="etch.cards.create",
        title="Etch: как создать карточку",
        text="# Etch: как создать карточку\n\nНажмите «Новая карточка».",
        source="content/ru/05-cards.md",
        score=0.9,
    )


@pytest.fixture
def reranked_hit():
    return RerankedHit(
        chunk_id="etch.cards.create",
        title="Etch: как создать карточку",
        text="# Etch: как создать карточку\n\nНажмите «Новая карточка».",
        source="content/ru/05-cards.md",
        score=0.9,
        rerank_score=4.5,
    )


@pytest.fixture
def reranker(reranked_hit):
    instance = Mock(spec=Reranker)
    instance.rerank.return_value = [reranked_hit]
    return instance


@pytest.fixture
def embedder():
    instance = Mock(spec=Embedder)
    instance.dimension = 2
    instance.embed_query.return_value = [1.0, 0.0]
    instance.embed_documents.return_value = [[1.0, 0.0]]
    return instance


@pytest.fixture
def store(hit):
    instance = Mock(spec=QdrantStore)
    instance.search.return_value = [hit]
    return instance


@pytest.fixture
def llm():
    instance = Mock(spec=LLM)
    instance.generate.return_value = "Нажмите «Новая карточка»."
    return instance


@pytest.fixture
def service(embedder, store, llm, reranker):
    return RagService(
        content_dir=Path("/guide/content/ru"),
        embedder=embedder,
        store=store,
        llm=llm,
        reranker=reranker,
        candidate_k=20,
        top_k=5,
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def cached_dependencies(monkeypatch):
    dependencies.clear_dependency_caches()
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.delenv("QDRANT_HTTP_PORT", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", PROJECT_DIR / ".env.example")
    monkeypatch.setenv("LLM_API_KEY", "test-api-key")
    yield
    try:
        if dependencies.get_resources.cache_info().currsize:
            dependencies.get_resources().close()
    finally:
        dependencies.clear_dependency_caches()


@pytest.fixture
def dependency_runtime(monkeypatch, cached_dependencies, reranked_hit):
    qdrant = Mock()
    llm_client = Mock()
    readiness_client = Mock()
    service = Mock(spec=RagService)
    service.ask.return_value = Answer(text="Нажмите «Новая карточка».", sources=[reranked_hit])
    factories = SimpleNamespace(
        qdrant=Mock(return_value=qdrant),
        llm_client=Mock(return_value=llm_client),
        readiness=Mock(return_value=readiness_client),
        embedder=Mock(),
        store=Mock(),
        llm=Mock(),
        reranker=Mock(),
        service=Mock(return_value=service),
    )
    monkeypatch.setattr(dependencies, "QdrantClient", factories.qdrant)
    monkeypatch.setattr(dependencies, "OpenAI", factories.llm_client)
    monkeypatch.setattr(dependencies.httpx, "Client", factories.readiness)
    monkeypatch.setattr(dependencies, "Embedder", factories.embedder)
    monkeypatch.setattr(dependencies, "QdrantStore", factories.store)
    monkeypatch.setattr(dependencies, "OpenAILLM", factories.llm)
    monkeypatch.setattr(dependencies, "Reranker", factories.reranker)
    monkeypatch.setattr(dependencies, "RagService", factories.service)
    return SimpleNamespace(
        qdrant=qdrant,
        llm_client=llm_client,
        readiness=readiness_client,
        service=service,
        factories=factories,
    )
