import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import httpx2 as httpx
import pytest
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.responses import ResponseUsage

from rag.errors import RagError
from rag.openai_llm import OpenAILLM


@pytest.fixture
def client():
    response = SimpleNamespace(
        id="resp_test", status="completed", output_text="Нажмите «Новая карточка».", usage=None
    )
    return SimpleNamespace(responses=SimpleNamespace(create=Mock(return_value=response)))


@pytest.fixture
def messages():
    return [
        {"role": "system", "content": "Отвечай по справке."},
        {"role": "user", "content": "Как создать карточку?"},
    ]


@pytest.fixture
def llm(client):
    return OpenAILLM(client=client, model="gpt-6-luna", reasoning_effort="high")


class TestGenerate:
    def test_returns_trimmed_text_and_forwards_messages_to_responses_api(
        self, llm, client, messages
    ):
        client.responses.create.return_value.output_text = "  Нажмите «Новая карточка». \n"

        result = llm.generate(messages)

        assert result == "Нажмите «Новая карточка»."
        client.responses.create.assert_called_once_with(
            model="gpt-6-luna",
            input=[
                {"role": "system", "content": "Отвечай по справке."},
                {"role": "user", "content": "Как создать карточку?"},
            ],
            stream=False,
            store=False,
            reasoning={"effort": "high"},
        )

    @pytest.mark.parametrize("text", ["", " \t\n"])
    def test_rejects_empty_model_answer(self, llm, client, messages, text):
        client.responses.create.return_value.output_text = text

        with pytest.raises(RagError, match="empty response"):
            llm.generate(messages)

    @pytest.mark.parametrize(
        "status", ["incomplete", "failed", "cancelled", "queued", "in_progress"]
    )
    def test_rejects_unfinished_response_even_with_partial_text(
        self, llm, client, messages, status
    ):
        client.responses.create.return_value.status = status
        client.responses.create.return_value.output_text = "Частичный"

        with pytest.raises(RagError, match="did not complete"):
            llm.generate(messages)

    @pytest.mark.parametrize(
        ("error_type", "expected"),
        [
            (APITimeoutError, "request timed out"),
            (APIConnectionError, "Failed to connect to OpenAI"),
        ],
    )
    def test_translates_transport_errors_and_logs_unknown_usage(
        self, llm, client, messages, error_type, expected, caplog
    ):
        client.responses.create.side_effect = error_type(
            request=httpx.Request("POST", "https://api.openai.com/v1/responses")
        )

        with pytest.raises(RagError, match=expected):
            llm.generate(messages)

        assert caplog.record_tuples == [
            (
                "rag.openai_llm",
                logging.WARNING,
                "LLM token usage unavailable model=gpt-6-luna reason=request_failed",
            )
        ]

    @pytest.mark.parametrize(
        ("error_type", "status_code", "expected"),
        [
            (AuthenticationError, 401, "access denied"),
            (PermissionDeniedError, 403, "access denied"),
            (NotFoundError, 404, "model or endpoint was not found"),
            (RateLimitError, 429, "rate limit or quota exceeded"),
            (APIStatusError, 400, "HTTP 400"),
            (APIStatusError, 500, "HTTP 500"),
        ],
    )
    def test_translates_api_errors_without_exposing_provider_body(
        self, llm, client, messages, error_type, status_code, expected, caplog
    ):
        response = httpx.Response(
            status_code,
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        )
        client.responses.create.side_effect = error_type(
            "private-provider-message", response=response, body={"key": "private-api-key"}
        )

        with pytest.raises(RagError, match=expected) as exc:
            llm.generate(messages)

        assert "private-provider-message" not in str(exc.value)
        assert "private-api-key" not in str(exc.value)
        assert "private-provider-message" not in caplog.text
        assert "private-api-key" not in caplog.text

    def test_translates_other_sdk_errors_without_exposing_provider_body(
        self, llm, client, messages
    ):
        client.responses.create.side_effect = APIError(
            "private-provider-message",
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
            body=None,
        )

        with pytest.raises(RagError, match="failed to generate a valid response") as exc:
            llm.generate(messages)

        assert "private-provider-message" not in str(exc.value)

    def test_returns_answer_and_logs_unknown_usage_when_provider_omits_usage(
        self, llm, client, messages, caplog
    ):
        result = llm.generate(messages)

        assert result == "Нажмите «Новая карточка»."
        assert caplog.record_tuples == [
            (
                "rag.openai_llm",
                logging.WARNING,
                "LLM token usage unavailable model=gpt-6-luna response_id=resp_test "
                "status=completed reason=missing_usage",
            )
        ]

    @pytest.mark.parametrize(
        ("status", "text", "expected_error"),
        [
            ("incomplete", "Частичный", "did not complete"),
            ("completed", "", "empty response"),
        ],
    )
    def test_logs_reported_usage_before_rejecting_response(
        self, llm, client, messages, caplog, status, text, expected_error
    ):
        response = client.responses.create.return_value
        response.status = status
        response.output_text = text
        response.usage = ResponseUsage(
            input_tokens=120,
            output_tokens=50,
            total_tokens=170,
            input_tokens_details={"cached_tokens": 20, "cache_write_tokens": 0},
            output_tokens_details={"reasoning_tokens": 30},
        )

        with caplog.at_level(logging.INFO, logger="rag.openai_llm"):
            with pytest.raises(RagError, match=expected_error):
                llm.generate(messages)

        assert caplog.record_tuples == [
            (
                "rag.openai_llm",
                logging.INFO,
                f"LLM token usage model=gpt-6-luna response_id=resp_test status={status} "
                "input_tokens=120 output_tokens=50 total_tokens=170 "
                "cached_input_tokens=20 reasoning_tokens=30",
            )
        ]


class TestResponsesContract:
    def test_uses_sdk_wire_format_collects_text_and_logs_reported_usage(self, messages, caplog):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "id": "resp_test",
                    "object": "response",
                    "created_at": 1,
                    "model": "gpt-6-luna",
                    "status": "completed",
                    "usage": {
                        "input_tokens": 120,
                        "output_tokens": 50,
                        "total_tokens": 170,
                        "input_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 0},
                        "output_tokens_details": {"reasoning_tokens": 30},
                    },
                    "output": [
                        {"id": "rs_test", "type": "reasoning", "summary": []},
                        {
                            "id": "msg_test",
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "  Нажмите ",
                                    "annotations": [],
                                },
                                {
                                    "type": "output_text",
                                    "text": "«Новая карточка». \n",
                                    "annotations": [],
                                },
                            ],
                        },
                    ],
                },
            )

        with OpenAI(
            api_key="test-api-key",
            base_url="https://llm.example/v1",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        ) as client:
            llm = OpenAILLM(client=client, model="gpt-6-luna", reasoning_effort="low")
            with caplog.at_level(logging.INFO, logger="rag.openai_llm"):
                result = llm.generate(messages)

        assert result == "Нажмите «Новая карточка»."
        assert len(requests) == 1
        assert requests[0].method == "POST"
        assert str(requests[0].url) == "https://llm.example/v1/responses"
        assert requests[0].headers["authorization"] == "Bearer test-api-key"
        assert json.loads(requests[0].content) == {
            "model": "gpt-6-luna",
            "input": [
                {"role": "system", "content": "Отвечай по справке."},
                {"role": "user", "content": "Как создать карточку?"},
            ],
            "stream": False,
            "store": False,
            "reasoning": {"effort": "low"},
        }
        usage_logs = [
            record.getMessage() for record in caplog.records if record.name == "rag.openai_llm"
        ]
        assert usage_logs == [
            "LLM token usage model=gpt-6-luna response_id=resp_test status=completed "
            "input_tokens=120 output_tokens=50 total_tokens=170 "
            "cached_input_tokens=20 reasoning_tokens=30"
        ]
