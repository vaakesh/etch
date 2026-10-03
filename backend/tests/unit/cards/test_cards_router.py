from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from app.auth.deps import get_current_user
from app.auth.errors import AccessTokenNotFoundError
from app.cards.errors import (
    CardAlreadyExistsError,
    CardNotFoundError,
    PermissionDeniedError,
)
from app.cards.schemas import CreateCardRequest, UpdateCardRequest
from tests.unit.factories import make_card


class TestCreateCard:
    async def test_creates_card_with_all_fields(
        self,
        client: AsyncClient,
        current_user,
        card_service: AsyncMock,
    ):
        payload = {
            "front_text": "доброе утро",
            "back_text": "good morning",
            "front_lang": "ru",
            "back_lang": "en",
        }
        created_card = make_card(**payload)
        card_service.create_card.return_value = created_card

        response = await client.post("/cards/", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": "доброе утро",
            "back_text": "good morning",
            "front_lang": "ru",
            "back_lang": "en",
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.create_card.assert_awaited_once_with(
            payload=CreateCardRequest(**payload),
            user_id=current_user.id,
        )

    async def test_applies_default_languages(
        self,
        client: AsyncClient,
        current_user,
        card_service: AsyncMock,
    ):
        payload = {
            "front_text": "привет",
            "back_text": "hello",
        }
        created_card = make_card()
        card_service.create_card.return_value = created_card

        response = await client.post("/cards/", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": "привет",
            "back_text": "hello",
            "front_lang": "ru",
            "back_lang": "en",
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.create_card.assert_awaited_once_with(
            payload=CreateCardRequest(
                front_text="привет",
                back_text="hello",
                front_lang="ru",
                back_lang="en",
            ),
            user_id=current_user.id,
        )

    async def test_normalizes_all_fields(
        self,
        client: AsyncClient,
        current_user,
        card_service: AsyncMock,
    ):
        payload = {
            "front_text": "  ДОБРОЕ УТРО  ",
            "back_text": "  GOOD MORNING  ",
            "front_lang": "  RU  ",
            "back_lang": "  EN  ",
        }
        created_card = make_card(
            front_text="ДОБРОЕ УТРО",
            back_text="GOOD MORNING",
            front_lang="ru",
            back_lang="en",
        )
        card_service.create_card.return_value = created_card

        response = await client.post("/cards/", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": "ДОБРОЕ УТРО",
            "back_text": "GOOD MORNING",
            "front_lang": "ru",
            "back_lang": "en",
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.create_card.assert_awaited_once_with(
            payload=CreateCardRequest(
                front_text="ДОБРОЕ УТРО",
                back_text="GOOD MORNING",
                front_lang="ru",
                back_lang="en",
            ),
            user_id=current_user.id,
        )

    @pytest.mark.parametrize(
        ("payload", "expected_front", "expected_back"),
        [
            pytest.param(
                {
                    "front_text": "a",
                    "back_text": "b",
                    "front_lang": "ru",
                    "back_lang": "en",
                },
                "a",
                "b",
                id="minimum_text_and_language_lengths",
            ),
            pytest.param(
                {
                    "front_text": "f" * 255,
                    "back_text": "b" * 255,
                    "front_lang": "rus",
                    "back_lang": "eng",
                },
                "f" * 255,
                "b" * 255,
                id="maximum_text_and_language_lengths",
            ),
        ],
    )
    async def test_accepts_boundary_payload(
        self,
        client: AsyncClient,
        current_user,
        payload,
        expected_front,
        expected_back,
        card_service: AsyncMock,
    ):
        created_card = make_card(
            front_text=expected_front,
            back_text=expected_back,
            front_lang=payload["front_lang"],
            back_lang=payload["back_lang"],
        )
        card_service.create_card.return_value = created_card

        response = await client.post("/cards/", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": expected_front,
            "back_text": expected_back,
            "front_lang": payload["front_lang"],
            "back_lang": payload["back_lang"],
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.create_card.assert_awaited_once_with(
            payload=CreateCardRequest(**payload),
            user_id=current_user.id,
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {
                    "front_text": "",
                    "back_text": "hello",
                    "front_lang": "ru",
                    "back_lang": "en",
                },
                {
                    "type": "string_too_short",
                    "loc": ["body", "front_text"],
                    "msg": "String should have at least 1 character",
                    "input": "",
                    "ctx": {"min_length": 1},
                },
                id="front_text_empty",
            ),
            pytest.param(
                {
                    "front_text": "привет",
                    "back_text": "b" * 256,
                    "front_lang": "ru",
                    "back_lang": "en",
                },
                {
                    "type": "string_too_long",
                    "loc": ["body", "back_text"],
                    "msg": "String should have at most 255 characters",
                    "input": "b" * 256,
                    "ctx": {"max_length": 255},
                },
                id="back_text_too_long",
            ),
            pytest.param(
                {
                    "front_text": "привет",
                    "back_text": "hello",
                    "front_lang": "r",
                    "back_lang": "en",
                },
                {
                    "type": "string_too_short",
                    "loc": ["body", "front_lang"],
                    "msg": "String should have at least 2 characters",
                    "input": "r",
                    "ctx": {"min_length": 2},
                },
                id="front_lang_too_short",
            ),
            pytest.param(
                {
                    "front_text": "привет",
                    "back_text": "hello",
                    "front_lang": "ru",
                    "back_lang": "engl",
                },
                {
                    "type": "string_too_long",
                    "loc": ["body", "back_lang"],
                    "msg": "String should have at most 3 characters",
                    "input": "engl",
                    "ctx": {"max_length": 3},
                },
                id="back_lang_too_long",
            ),
            pytest.param(
                {
                    "front_text": None,
                    "back_text": "hello",
                    "front_lang": "ru",
                    "back_lang": "en",
                },
                {
                    "type": "string_type",
                    "loc": ["body", "front_text"],
                    "msg": "Input should be a valid string",
                    "input": None,
                },
                id="front_text_null",
            ),
        ],
    )
    async def test_rejects_invalid_payload(
        self,
        client: AsyncClient,
        payload,
        expected_detail,
        card_service: AsyncMock,
    ):
        response = await client.post("/cards/", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        card_service.create_card.assert_not_awaited()

    @pytest.mark.parametrize(
        ("payload", "expected_details"),
        [
            pytest.param(
                {"back_text": "hello"},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "front_text"],
                        "msg": "Field required",
                        "input": {"back_text": "hello"},
                    }
                ],
                id="front_text_missing",
            ),
            pytest.param(
                {"front_text": "привет"},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "back_text"],
                        "msg": "Field required",
                        "input": {"front_text": "привет"},
                    }
                ],
                id="back_text_missing",
            ),
            pytest.param(
                {},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "front_text"],
                        "msg": "Field required",
                        "input": {},
                    },
                    {
                        "type": "missing",
                        "loc": ["body", "back_text"],
                        "msg": "Field required",
                        "input": {},
                    },
                ],
                id="both_texts_missing",
            ),
        ],
    )
    async def test_rejects_missing_fields(
        self,
        client: AsyncClient,
        payload,
        expected_details,
        card_service: AsyncMock,
    ):
        response = await client.post("/cards/", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": expected_details,
        }

        card_service.create_card.assert_not_awaited()

    async def test_returns_409_when_card_already_exists(
        self,
        client: AsyncClient,
        current_user,
        card_service: AsyncMock,
    ):
        payload = {
            "front_text": "привет",
            "back_text": "hello",
        }
        card_service.create_card.side_effect = CardAlreadyExistsError()

        response = await client.post("/cards/", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "code": "CARD_ALREADY_EXISTS",
            "message": "Card already exists",
        }

        card_service.create_card.assert_awaited_once_with(
            payload=CreateCardRequest(**payload),
            user_id=current_user.id,
        )


class TestUpdateCard:
    async def test_updates_all_card_fields(
        self,
        client: AsyncClient,
        current_user,
        card,
        card_service: AsyncMock,
    ):
        payload = {
            "front_text": "доброе утро",
            "back_text": "good morning",
            "front_lang": "rus",
            "back_lang": "eng",
        }
        updated_card = make_card(**payload)
        card_service.update_card.return_value = updated_card

        response = await client.patch(f"/cards/{card.uuid}", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": "доброе утро",
            "back_text": "good morning",
            "front_lang": "rus",
            "back_lang": "eng",
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.update_card.assert_awaited_once_with(
            card.uuid,
            current_user.id,
            UpdateCardRequest(**payload),
        )

    @pytest.mark.parametrize(
        (
            "payload",
            "expected_front",
            "expected_back",
            "expected_front_lang",
            "expected_back_lang",
        ),
        [
            pytest.param(
                {"front_text": "доброе утро"},
                "доброе утро",
                "hello",
                "ru",
                "en",
                id="front_text_only",
            ),
            pytest.param(
                {"back_text": "good morning"},
                "привет",
                "good morning",
                "ru",
                "en",
                id="back_text_only",
            ),
            pytest.param(
                {"front_lang": "rus"},
                "привет",
                "hello",
                "rus",
                "en",
                id="front_lang_only",
            ),
            pytest.param(
                {"back_lang": "eng"},
                "привет",
                "hello",
                "ru",
                "eng",
                id="back_lang_only",
            ),
        ],
    )
    async def test_updates_single_field(
        self,
        client: AsyncClient,
        current_user,
        card,
        payload,
        expected_front,
        expected_back,
        expected_front_lang,
        expected_back_lang,
        card_service: AsyncMock,
    ):
        updated_card = make_card(
            front_text=expected_front,
            back_text=expected_back,
            front_lang=expected_front_lang,
            back_lang=expected_back_lang,
        )
        card_service.update_card.return_value = updated_card

        response = await client.patch(f"/cards/{card.uuid}", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": expected_front,
            "back_text": expected_back,
            "front_lang": expected_front_lang,
            "back_lang": expected_back_lang,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.update_card.assert_awaited_once_with(
            card.uuid,
            current_user.id,
            UpdateCardRequest(**payload),
        )

    async def test_passes_empty_update_payload(
        self,
        client: AsyncClient,
        current_user,
        card,
        card_service: AsyncMock,
    ):
        card_service.update_card.return_value = card

        response = await client.patch(f"/cards/{card.uuid}", json={})

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": "привет",
            "back_text": "hello",
            "front_lang": "ru",
            "back_lang": "en",
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.update_card.assert_awaited_once_with(
            card.uuid,
            current_user.id,
            UpdateCardRequest(),
        )

    @pytest.mark.parametrize("field", ["front_text", "back_text", "front_lang", "back_lang"])
    async def test_rejects_explicit_null(self, client, card, card_service, field):
        response = await client.patch(f"/cards/{card.uuid}", json={field: None})

        assert response.status_code == 422
        assert response.json() == {
            "code": "VALIDATION_ERROR", "message": "Validation error",
            "details": [{"type": "value_error", "loc": ["body", field],
                         "msg": f"{field} value cannot be null", "input": None}],
        }
        card_service.update_card.assert_not_awaited()

    async def test_normalizes_all_updated_fields(
        self,
        client: AsyncClient,
        current_user,
        card,
        card_service: AsyncMock,
    ):
        payload = {
            "front_text": "  ДОБРОЕ УТРО  ",
            "back_text": "  GOOD MORNING  ",
            "front_lang": "  RU  ",
            "back_lang": "  EN  ",
        }
        updated_card = make_card(
            front_text="ДОБРОЕ УТРО",
            back_text="GOOD MORNING",
            front_lang="ru",
            back_lang="en",
        )
        card_service.update_card.return_value = updated_card

        response = await client.patch(f"/cards/{card.uuid}", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": "ДОБРОЕ УТРО",
            "back_text": "GOOD MORNING",
            "front_lang": "ru",
            "back_lang": "en",
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.update_card.assert_awaited_once_with(
            card.uuid,
            current_user.id,
            UpdateCardRequest(
                front_text="ДОБРОЕ УТРО",
                back_text="GOOD MORNING",
                front_lang="ru",
                back_lang="en",
            ),
        )

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(
                {
                    "front_text": "a",
                    "back_text": "b",
                    "front_lang": "ru",
                    "back_lang": "en",
                },
                id="minimum_text_and_language_lengths",
            ),
            pytest.param(
                {
                    "front_text": "f" * 255,
                    "back_text": "b" * 255,
                    "front_lang": "rus",
                    "back_lang": "eng",
                },
                id="maximum_text_and_language_lengths",
            ),
        ],
    )
    async def test_accepts_boundary_payload(
        self,
        client: AsyncClient,
        current_user,
        card,
        payload,
        card_service: AsyncMock,
    ):
        updated_card = make_card(**payload)
        card_service.update_card.return_value = updated_card

        response = await client.patch(f"/cards/{card.uuid}", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000100",
            "front_text": payload["front_text"],
            "back_text": payload["back_text"],
            "front_lang": payload["front_lang"],
            "back_lang": payload["back_lang"],
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.update_card.assert_awaited_once_with(
            card.uuid,
            current_user.id,
            UpdateCardRequest(**payload),
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {"front_text": ""},
                {
                    "type": "string_too_short",
                    "loc": ["body", "front_text", "constrained-str"],
                    "msg": "String should have at least 1 character",
                    "input": "",
                    "ctx": {"min_length": 1},
                },
                id="front_text_empty",
            ),
            pytest.param(
                {"back_text": "b" * 256},
                {
                    "type": "string_too_long",
                    "loc": ["body", "back_text", "constrained-str"],
                    "msg": "String should have at most 255 characters",
                    "input": "b" * 256,
                    "ctx": {"max_length": 255},
                },
                id="back_text_too_long",
            ),
            pytest.param(
                {"front_lang": "r"},
                {
                    "type": "string_too_short",
                    "loc": ["body", "front_lang", "constrained-str"],
                    "msg": "String should have at least 2 characters",
                    "input": "r",
                    "ctx": {"min_length": 2},
                },
                id="front_lang_too_short",
            ),
            pytest.param(
                {"back_lang": "engl"},
                {
                    "type": "string_too_long",
                    "loc": ["body", "back_lang", "constrained-str"],
                    "msg": "String should have at most 3 characters",
                    "input": "engl",
                    "ctx": {"max_length": 3},
                },
                id="back_lang_too_long",
            ),
        ],
    )
    async def test_rejects_invalid_payload(
        self,
        client: AsyncClient,
        card,
        payload,
        expected_detail,
        card_service: AsyncMock,
    ):
        response = await client.patch(f"/cards/{card.uuid}", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                expected_detail,
                {"type": "none_required",
                 "loc": ["body", expected_detail["loc"][1], "none"],
                 "msg": "Input should be None", "input": expected_detail["input"]},
            ],
        }

        card_service.update_card.assert_not_awaited()

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                CardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "CARD_NOT_FOUND",
                "Card not found",
                id="card_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "CARD_PERMISSION_DENIED",
                "Permission denied",
                id="permission_denied",
            ),
            pytest.param(
                CardAlreadyExistsError(),
                status.HTTP_409_CONFLICT,
                "CARD_ALREADY_EXISTS",
                "Card already exists",
                id="card_already_exists",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        card,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        card_service: AsyncMock,
    ):
        payload = {"front_text": "доброе утро"}
        card_service.update_card.side_effect = service_error

        response = await client.patch(f"/cards/{card.uuid}", json=payload)

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        card_service.update_card.assert_awaited_once_with(
            card.uuid,
            current_user.id,
            UpdateCardRequest(**payload),
        )

    async def test_rejects_invalid_card_uuid(
        self,
        client: AsyncClient,
        card_service: AsyncMock,
    ):
        response = await client.patch(
            "/cards/not-a-uuid",
            json={"front_text": "доброе утро"},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "card_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        card_service.update_card.assert_not_awaited()


class TestDeleteCard:
    async def test_deletes_card(
        self,
        client: AsyncClient,
        current_user,
        card,
        card_service: AsyncMock,
    ):
        response = await client.delete(f"/cards/{card.uuid}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        card_service.delete_card.assert_awaited_once_with(
            user_id=current_user.id,
            card_uuid=card.uuid,
        )

    async def test_returns_404_when_card_not_found(
        self,
        client: AsyncClient,
        current_user,
        card,
        card_service: AsyncMock,
    ):
        card_service.delete_card.side_effect = CardNotFoundError()

        response = await client.delete(f"/cards/{card.uuid}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "code": "CARD_NOT_FOUND",
            "message": "Card not found",
        }

        card_service.delete_card.assert_awaited_once_with(
            user_id=current_user.id,
            card_uuid=card.uuid,
        )

    async def test_rejects_invalid_card_uuid(
        self,
        client: AsyncClient,
        card_service: AsyncMock,
    ):
        response = await client.delete("/cards/not-a-uuid")

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "card_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        card_service.delete_card.assert_not_awaited()


class TestCardAuthentication:
    @pytest.mark.parametrize(("method", "path", "payload"), [
        ("POST", "/cards/", {"front_text": "привет", "back_text": "hello"}),
        ("PATCH", "/cards/0198ad01-b200-7000-8000-000000000100", {}),
        ("DELETE", "/cards/0198ad01-b200-7000-8000-000000000100", None),
    ])
    async def test_returns_401_without_calling_card_service(
        self, app, client, card_service, monkeypatch, method, path, payload,
    ):
        async def reject_unauthenticated_user():
            raise AccessTokenNotFoundError()

        monkeypatch.setitem(
            app.dependency_overrides, get_current_user, reject_unauthenticated_user,
        )

        response = await client.request(method, path, json=payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {
            "code": "ACCESS_TOKEN_NOT_FOUND",
            "message": "Not authorized",
        }
        assert card_service.mock_calls == []
