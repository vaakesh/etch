import asyncio
from contextlib import ExitStack
from functools import lru_cache

import httpx
from openai import OpenAI
from qdrant_client import QdrantClient

from rag.config import get_settings
from rag.embedder import Embedder
from rag.openai_llm import OpenAILLM
from rag.reranker import Reranker
from rag.service import RagService
from rag.store import QdrantStore


@lru_cache(maxsize=1)
def get_resources() -> ExitStack:
    return ExitStack()


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    client = QdrantClient(
        url=str(settings.qdrant_url),
        grpc_port=settings.qdrant_grpc_port,
        timeout=settings.qdrant_timeout,
        check_compatibility=False,
    )
    get_resources().callback(client.close)
    return client


@lru_cache(maxsize=1)
def get_llm_client() -> OpenAI:
    settings = get_settings()
    client = OpenAI(
        base_url=str(settings.llm_url),
        api_key=settings.llm_api_key.get_secret_value(),
        timeout=settings.llm_timeout,
    )
    get_resources().callback(client.close)
    return client


@lru_cache(maxsize=1)
def get_readiness_client() -> httpx.Client:
    client = httpx.Client()
    get_resources().callback(client.close)
    return client


@lru_cache(maxsize=1)
def get_rag_service() -> RagService:
    """Build the process-wide service for FastAPI startup and request dependencies."""
    settings = get_settings()
    qdrant_client = get_qdrant_client()
    llm_client = get_llm_client()
    return RagService(
        content_dir=settings.content_dir,
        embedder=Embedder(model_name=settings.embedding_model, device=settings.embedding_device),
        store=QdrantStore(client=qdrant_client, collection=settings.qdrant_collection),
        llm=OpenAILLM(
            client=llm_client,
            model=settings.llm_model,
            reasoning_effort=settings.llm_reasoning_effort,
        ),
        reranker=Reranker(
            model_name=settings.reranker_model,
            device=settings.reranker_device,
            dtype=settings.reranker_dtype,
            batch_size=settings.reranker_batch_size,
            max_length=settings.reranker_max_length,
        ),
        candidate_k=settings.candidate_k,
        top_k=settings.top_k,
    )


@lru_cache(maxsize=1)
def get_ask_lock() -> asyncio.Lock:
    return asyncio.Lock()


def clear_dependency_caches() -> None:
    """Drop references only after ExitStack has attempted to close every client."""
    get_rag_service.cache_clear()
    get_ask_lock.cache_clear()
    get_llm_client.cache_clear()
    get_readiness_client.cache_clear()
    get_qdrant_client.cache_clear()
    get_settings.cache_clear()
    get_resources.cache_clear()
