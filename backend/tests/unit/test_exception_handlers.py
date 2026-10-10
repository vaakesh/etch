from collections import Counter

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.decks.errors import DeckNotFoundError, DeckSizeLimitExceededError
from app.errors import RequestValueError
from app.exception_handlers import ERROR_RESPONSES, register_exception_handlers
from app.redis.errors import RateLimitError
from app.training_sessions.errors import (
    TrainingSessionDeckArchivedError,
    TrainingSessionDeckUnavailableError,
)


EXTRA_ARGS: dict[type[Exception], tuple] = {
    DeckSizeLimitExceededError: (5000, 100, 1),
}


def instantiate(exception_class: type[Exception]) -> Exception:
    return exception_class(*EXTRA_ARGS.get(exception_class, ()))


def build_app(raised_error: Exception) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise raised_error

    return app


async def request_error(raised_error: Exception) -> tuple[int, dict]:
    app = build_app(raised_error)
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    return response.status_code, response.json()


class TestErrorCodeTable:
    def test_every_error_has_a_unique_code(self):
        codes = [code for _, _, code in ERROR_RESPONSES]
        duplicates = [code for code, count in Counter(codes).items() if count > 1]

        assert duplicates == []

    def test_every_error_class_is_mapped_once(self):
        classes = [exception_class for exception_class, _, _ in ERROR_RESPONSES]
        duplicates = [
            exception_class.__name__
            for exception_class, count in Counter(classes).items()
            if count > 1
        ]

        assert duplicates == []

    def test_codes_are_screaming_snake_case(self):
        for _, _, code in ERROR_RESPONSES:
            assert code.isupper()
            assert code.replace("_", "").isalnum()


class TestErrorResponseShape:
    @pytest.mark.parametrize(
        ("error", "expected_status", "expected_payload"),
        [
            pytest.param(
                TrainingSessionDeckArchivedError(),
                409,
                {
                    "code": "TRAINING_SESSION_DECK_ARCHIVED",
                    "message": "Save the archived deck before continuing this session",
                },
                id="archived_deck",
            ),
            pytest.param(
                TrainingSessionDeckUnavailableError(),
                410,
                {
                    "code": "TRAINING_SESSION_DECK_UNAVAILABLE",
                    "message": "The session deck was deleted or its archive expired",
                },
                id="unavailable_deck",
            ),
        ],
    )
    async def test_returns_session_deck_error_contract(
        self, error, expected_status, expected_payload,
    ):
        status_code, payload = await request_error(error)

        assert status_code == expected_status
        assert payload == expected_payload

    @pytest.mark.parametrize(
        ("exception_class", "expected_status", "expected_code"),
        ERROR_RESPONSES,
    )
    async def test_returns_the_mapped_status_and_code(
        self,
        exception_class,
        expected_status,
        expected_code,
    ):
        status_code, payload = await request_error(instantiate(exception_class))

        assert status_code == expected_status
        assert payload["code"] == expected_code
        assert isinstance(payload["message"], str)

    async def test_distinguishes_two_conflicts_that_share_a_status(self):
        _, already_exists = await request_error(DeckNotFoundError())
        deck_full_status, deck_full = await request_error(
            DeckSizeLimitExceededError(limit=5000, current=5000, requested=1),
        )

        assert deck_full_status == status.HTTP_409_CONFLICT
        assert deck_full["code"] == "DECK_SIZE_LIMIT_EXCEEDED"
        assert already_exists["code"] != deck_full["code"]

    async def test_rate_limit_error_keeps_its_code(self):
        status_code, payload = await request_error(RateLimitError())

        assert status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert payload["code"] == "RATE_LIMIT_EXCEEDED"

    async def test_request_value_error_is_reported_as_validation(self):
        status_code, payload = await request_error(
            RequestValueError("Answer must not be empty", failed_field="answer"),
        )

        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert payload["code"] == "VALIDATION_ERROR"
        assert payload["details"][0]["loc"] == ["body", "answer"]

    @pytest.mark.parametrize(
        "error_type",
        [RedisError, RedisConnectionError, RedisTimeoutError],
        ids=["redis_error", "connection_error", "timeout_error"],
    )
    async def test_redis_error_is_reported_as_service_unavailable(self, error_type):
        app = build_app(error_type("redis://admin:secret@redis:6379 is down"))
        transport = ASGITransport(app=app, raise_app_exceptions=False)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/boom")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json() == {
            "code": "SERVICE_UNAVAILABLE",
            "message": "Service is temporarily unavailable",
        }
        assert response.headers["Retry-After"] == "5"

    async def test_unhandled_error_does_not_leak_internals(self):
        status_code, payload = await request_error(RuntimeError("secret table name"))

        assert status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert payload == {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error",
        }
