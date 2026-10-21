import pytest

from app.auth.deps import get_current_user
from app.auth.errors import AccessTokenNotFoundError
from app.rag.errors import RagBadResponseError, RagTimeoutError, RagUnavailableError
from app.rag.schemas import AskMessageResponse


class TestAsk:
    async def test_returns_only_answer_text(self, client, rag_client):
        rag_client.ask.return_value = AskMessageResponse(
            text="Откройте раздел импорта.",
        )

        response = await client.post("/ask", json={"message": "Как импортировать карточки?"})

        assert response.status_code == 200
        assert response.json() == {
            "text": "Откройте раздел импорта.",
        }
        rag_client.ask.assert_awaited_once_with("Как импортировать карточки?")

    @pytest.mark.parametrize(
        ("error", "expected_status", "expected_payload"),
        [
            pytest.param(
                RagUnavailableError(), 503,
                {"code": "RAG_UNAVAILABLE", "message": "Assistant is temporarily unavailable"},
                id="unavailable",
            ),
            pytest.param(
                RagTimeoutError(), 504,
                {"code": "RAG_TIMEOUT", "message": "Assistant response timed out"},
                id="timeout",
            ),
            pytest.param(
                RagBadResponseError(), 502,
                {"code": "RAG_BAD_RESPONSE", "message": "Assistant returned an invalid response"},
                id="invalid_response",
            ),
        ],
    )
    async def test_returns_registered_rag_error_contract(
        self, client, rag_client, error, expected_status, expected_payload,
    ):
        rag_client.ask.side_effect = error

        response = await client.post("/ask", json={"message": "Как импортировать карточки?"})

        assert response.status_code == expected_status
        assert response.json() == expected_payload
        rag_client.ask.assert_awaited_once_with("Как импортировать карточки?")

    async def test_rejects_unauthenticated_request(self, client, app, rag_client):
        async def require_login():
            raise AccessTokenNotFoundError()

        app.dependency_overrides[get_current_user] = require_login

        response = await client.post("/ask", json={"message": "Как импортировать карточки?"})

        assert response.status_code == 401
        assert response.json() == {
            "code": "ACCESS_TOKEN_NOT_FOUND", "message": "Not authorized",
        }
        rag_client.ask.assert_not_awaited()

    async def test_rejects_rate_limited_request(self, client, rag_client, redis_rate_limiter):
        redis_rate_limiter.check.return_value = False

        response = await client.post("/ask", json={"message": "Как импортировать карточки?"})

        assert response.status_code == 429
        assert response.json() == {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
        }
        rag_client.ask.assert_not_awaited()
