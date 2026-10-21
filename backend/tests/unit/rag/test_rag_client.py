from unittest.mock import create_autospec

import httpx
import pytest

from app.rag.client import RagClient
from app.rag.errors import RagBadResponseError


class TestAsk:
    async def test_returns_only_text_when_rag_response_contains_sources(self):
        http = create_autospec(httpx.AsyncClient, instance=True)
        http.post.return_value = httpx.Response(200, json={
            "text": "Откройте раздел импорта.",
            "sources": [{
                "chunk_id": "etch.import",
                "title": "Импорт",
                "text": "Как импортировать карточки",
                "source": "content/ru/06-import.md",
                "score": 0.8,
                "rerank_score": 0.9,
            }],
        })
        client = RagClient(http, request_timeout=60)

        response = await client.ask("Как импортировать карточки?")

        assert response.model_dump() == {"text": "Откройте раздел импорта."}

    async def test_rejects_invalid_sources_even_when_text_is_valid(self):
        http = create_autospec(httpx.AsyncClient, instance=True)
        http.post.return_value = httpx.Response(200, json={
            "text": "Откройте раздел импорта.",
            "sources": [{"chunk_id": "etch.import"}],
        })
        client = RagClient(http, request_timeout=60)

        with pytest.raises(RagBadResponseError):
            await client.ask("Как импортировать карточки?")
