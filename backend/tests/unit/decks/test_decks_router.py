from unittest.mock import AsyncMock
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient

from app.auth.deps import get_current_user
from app.auth.errors import AccessTokenNotFoundError
from app.cards.errors import CardNotFoundError
from app.cards.schemas import CreateCardRequest
from app.decks.errors import (
    CannotFavouriteUnsavedDeckError,
    CannotSaveOwnDeckError,
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckIsNotSavedError,
    DeckNotFoundError,
    DeckNotArchivedError,
    DeckSizeLimitExceededError,
    InvalidDeckCardPositionError,
    PermissionDeniedError,
)
from app.decks.schemas import CreateDeckRequest, UpdateDeckRequest
from app.decks.archiver import ArchiveExpiredError
from tests.unit.factories import (
    make_card,
    make_deck,
    make_deck_card,
    make_user_deck,
)


class TestGetDeck:
    async def test_returns_deck_for_authenticated_viewer(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_visible_by_uuid.return_value = deck

        response = await client.get(f"/decks/{deck.uuid}")

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": "Test deck",
            "description": "Test deck description",
            "words_count": 10,
            "is_public": True,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.get_visible_by_uuid.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            viewer_id=current_user.id,
        )

    @pytest.mark.parametrize("optional_current_user", [None], indirect=True)
    async def test_returns_public_deck_for_anonymous_viewer(
        self,
        client: AsyncClient,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_visible_by_uuid.return_value = deck

        response = await client.get(f"/decks/{deck.uuid}")

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": "Test deck",
            "description": "Test deck description",
            "words_count": 10,
            "is_public": True,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.get_visible_by_uuid.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            viewer_id=None,
        )

    async def test_returns_404_when_deck_not_found(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        deck_service.get_visible_by_uuid.side_effect = DeckNotFoundError()

        response = await client.get("/decks/0198ad01-b200-7000-8000-000000000200")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "code": "DECK_NOT_FOUND",
            "message": "Deck not found",
        }

        deck_service.get_visible_by_uuid.assert_awaited_once_with(
            deck_uuid=UUID("0198ad01-b200-7000-8000-000000000200"),
            viewer_id=42,
        )

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.get("/decks/not-a-uuid")

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "deck_uuid"],
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

        deck_service.get_visible_by_uuid.assert_not_awaited()


class TestCreateDeck:
    async def test_creates_deck_with_all_fields(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        payload = {
            "title": "Vocabulary",
            "description": "Words for the next lesson",
            "is_public": True,
        }
        created_deck = make_deck(**payload)
        deck_service.create_deck.return_value = created_deck

        response = await client.post("/decks/create", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": "Vocabulary",
            "description": "Words for the next lesson",
            "words_count": 10,
            "is_public": True,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.create_deck.assert_awaited_once_with(
            CreateDeckRequest(**payload),
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            user_username=current_user.username,
        )

    async def test_applies_optional_field_defaults(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        payload = {"title": "Vocabulary"}
        created_deck = make_deck(
            title="Vocabulary",
            description=None,
            is_public=False,
        )
        deck_service.create_deck.return_value = created_deck

        response = await client.post("/decks/create", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": "Vocabulary",
            "description": None,
            "words_count": 10,
            "is_public": False,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.create_deck.assert_awaited_once_with(
            CreateDeckRequest(
                title="Vocabulary",
                description=None,
                is_public=False,
            ),
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            user_username=current_user.username,
        )

    async def test_normalizes_title_and_description(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        payload = {
            "title": "  Vocabulary  ",
            "description": "  Words for the next lesson  ",
            "is_public": False,
        }
        created_deck = make_deck(
            title="Vocabulary",
            description="Words for the next lesson",
            is_public=False,
        )
        deck_service.create_deck.return_value = created_deck

        response = await client.post("/decks/create", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": "Vocabulary",
            "description": "Words for the next lesson",
            "words_count": 10,
            "is_public": False,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.create_deck.assert_awaited_once_with(
            CreateDeckRequest(
                title="Vocabulary",
                description="Words for the next lesson",
                is_public=False,
            ),
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            user_username=current_user.username,
        )

    @pytest.mark.parametrize(
        ("title", "description", "expected_description"),
        [
            pytest.param("abc", "", None, id="minimum_title_and_empty_description"),
            pytest.param(
                "a" * 50,
                "d" * 3000,
                "d" * 3000,
                id="maximum_title_and_description",
            ),
        ],
    )
    async def test_accepts_boundary_payload(
        self,
        client: AsyncClient,
        current_user,
        title,
        description,
        expected_description,
        deck_service: AsyncMock,
    ):
        payload = {
            "title": title,
            "description": description,
            "is_public": False,
        }
        created_deck = make_deck(
            title=title,
            description=description,
            is_public=False,
        )
        deck_service.create_deck.return_value = created_deck

        response = await client.post("/decks/create", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": title,
            "description": expected_description,
            "words_count": 10,
            "is_public": False,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.create_deck.assert_awaited_once_with(
            CreateDeckRequest(**payload),
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            user_username=current_user.username,
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {"title": "ab"},
                {
                    "type": "string_too_short",
                    "loc": ["body", "title"],
                    "msg": "String should have at least 3 characters",
                    "input": "ab",
                    "ctx": {"min_length": 3},
                },
                id="title_too_short",
            ),
            pytest.param(
                {"title": "a" * 51},
                {
                    "type": "string_too_long",
                    "loc": ["body", "title"],
                    "msg": "String should have at most 50 characters",
                    "input": "a" * 51,
                    "ctx": {"max_length": 50},
                },
                id="title_too_long",
            ),
            pytest.param(
                {"title": "Vocabulary", "description": "d" * 3001},
                {
                    "type": "string_too_long",
                    "loc": ["body", "description"],
                    "msg": "String should have at most 3000 characters",
                    "input": "d" * 3001,
                    "ctx": {"max_length": 3000},
                },
                id="description_too_long",
            ),
        ],
    )
    async def test_rejects_invalid_payload(
        self,
        client: AsyncClient,
        payload,
        expected_detail,
        deck_service: AsyncMock,
    ):
        response = await client.post("/decks/create", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.create_deck.assert_not_awaited()

    async def test_rejects_missing_title(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.post("/decks/create", json={})

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "missing",
                    "loc": ["body", "title"],
                    "msg": "Field required",
                    "input": {},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        deck_service.create_deck.assert_not_awaited()

    async def test_returns_409_when_deck_already_exists(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        payload = {"title": "Vocabulary"}
        deck_service.create_deck.side_effect = DeckAlreadyExistsError()

        response = await client.post("/decks/create", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "code": "DECK_ALREADY_EXISTS",
            "message": "Deck already exists",
        }

        deck_service.create_deck.assert_awaited_once_with(
            CreateDeckRequest(**payload),
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            user_username=current_user.username,
        )


class TestUpdateDeck:
    async def test_updates_all_deck_fields(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        payload = {
            "title": "Updated deck",
            "description": "Updated description",
            "is_public": False,
        }
        updated_deck = make_deck(**payload)
        deck_service.update_deck.return_value = updated_deck

        response = await client.patch(f"/decks/{deck.uuid}", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": "Updated deck",
            "description": "Updated description",
            "words_count": 10,
            "is_public": False,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.update_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            payload=UpdateDeckRequest(**payload),
        )

    @pytest.mark.parametrize(
        ("payload", "expected_title", "expected_description", "expected_public"),
        [
            pytest.param(
                {"title": "Renamed deck"},
                "Renamed deck",
                "Test deck description",
                True,
                id="title_only",
            ),
            pytest.param(
                {"description": None},
                "Test deck",
                None,
                True,
                id="clear_description",
            ),
            pytest.param(
                {"is_public": False},
                "Test deck",
                "Test deck description",
                False,
                id="visibility_only",
            ),
        ],
    )
    async def test_updates_single_field(
        self,
        client: AsyncClient,
        current_user,
        deck,
        payload,
        expected_title,
        expected_description,
        expected_public,
        deck_service: AsyncMock,
    ):
        updated_deck = make_deck(
            title=expected_title,
            description=expected_description,
            is_public=expected_public,
        )
        deck_service.update_deck.return_value = updated_deck

        response = await client.patch(f"/decks/{deck.uuid}", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": expected_title,
            "description": expected_description,
            "words_count": 10,
            "is_public": expected_public,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.update_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            payload=UpdateDeckRequest(**payload),
        )

    async def test_passes_empty_update_payload(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.update_deck.return_value = deck

        response = await client.patch(f"/decks/{deck.uuid}", json={})

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": "Test deck",
            "description": "Test deck description",
            "words_count": 10,
            "is_public": True,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.update_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            payload=UpdateDeckRequest(),
        )

    async def test_normalizes_updated_text_fields(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        payload = {
            "title": "  Updated deck  ",
            "description": "  Updated description  ",
        }
        updated_deck = make_deck(
            title="Updated deck",
            description="Updated description",
        )
        deck_service.update_deck.return_value = updated_deck

        response = await client.patch(f"/decks/{deck.uuid}", json=payload)

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000200",
            "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
            "owner_username": "test-user",
            "title": "Updated deck",
            "description": "Updated description",
            "words_count": 10,
            "is_public": True,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.update_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            payload=UpdateDeckRequest(
                title="Updated deck",
                description="Updated description",
            ),
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {"title": "ab"},
                [{
                    "type": "string_too_short",
                    "loc": ["body", "title", "constrained-str"],
                    "msg": "String should have at least 3 characters",
                    "input": "ab",
                    "ctx": {"min_length": 3},
                }, {"type": "none_required", "loc": ["body", "title", "none"], "msg": "Input should be None", "input": "ab"}],
                id="title_too_short",
            ),
            pytest.param(
                {"title": "a" * 51},
                [{
                    "type": "string_too_long",
                    "loc": ["body", "title", "constrained-str"],
                    "msg": "String should have at most 50 characters",
                    "input": "a" * 51,
                    "ctx": {"max_length": 50},
                }, {"type": "none_required", "loc": ["body", "title", "none"], "msg": "Input should be None", "input": "a" * 51}],
                id="title_too_long",
            ),
            pytest.param(
                {"description": "d" * 3001},
                [{
                    "type": "string_too_long",
                    "loc": ["body", "description"],
                    "msg": "String should have at most 3000 characters",
                    "input": "d" * 3001,
                    "ctx": {"max_length": 3000},
                }],
                id="description_too_long",
            ),
        ],
    )
    async def test_rejects_invalid_payload(
        self,
        client: AsyncClient,
        deck,
        payload,
        expected_detail,
        deck_service: AsyncMock,
    ):
        response = await client.patch(f"/decks/{deck.uuid}", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": expected_detail,
        }

        deck_service.update_deck.assert_not_awaited()

    @pytest.mark.parametrize("field", ["title", "is_public"])
    async def test_rejects_null_for_non_nullable_field(
        self,
        client: AsyncClient,
        deck,
        field,
        deck_service: AsyncMock,
    ):
        response = await client.patch(
            f"/decks/{deck.uuid}",
            json={field: None},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "value_error",
                    "loc": ["body", field],
                    "msg": f"{field} value cannot be null",
                    "input": None,
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        deck_service.update_deck.assert_not_awaited()

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                DeckAlreadyExistsError(),
                status.HTTP_409_CONFLICT,
                "DECK_ALREADY_EXISTS",
                "Deck already exists",
                id="deck_already_exists",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        deck_service: AsyncMock,
    ):
        payload = {"title": "Updated deck"}
        deck_service.update_deck.side_effect = service_error

        response = await client.patch(f"/decks/{deck.uuid}", json=payload)

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        deck_service.update_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            payload=UpdateDeckRequest(**payload),
        )

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.patch(
            "/decks/not-a-uuid",
            json={"title": "Updated deck"},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "deck_uuid"],
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

        deck_service.update_deck.assert_not_awaited()


class TestDeleteDeck:
    async def test_deletes_deck(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        response = await client.delete(f"/decks/{deck.uuid}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        deck_service.delete_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            user_id=current_user.id,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        deck_service: AsyncMock,
    ):
        deck_service.delete_deck.side_effect = service_error

        response = await client.delete(f"/decks/{deck.uuid}")

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        deck_service.delete_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            user_id=current_user.id,
        )

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.delete("/decks/not-a-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "deck_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        deck_service.delete_deck.assert_not_awaited()


class TestGetDeckCards:
    async def test_returns_deck_cards_with_default_pagination(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        first_card = make_card()
        second_card = make_card(
            uuid=UUID("0198ad01-b200-7000-8000-000000000101"),
            front_text="пока",
            back_text="bye",
            front_lang="ru",
            back_lang="en",
        )
        deck_service.get_deck_cards.return_value = [first_card, second_card]

        response = await client.get(f"/decks/{deck.uuid}/cards")

        expected = [
            {
                "uuid": "0198ad01-b200-7000-8000-000000000100",
                "front_text": "привет",
                "back_text": "hello",
                "front_lang": "ru",
                "back_lang": "en",
                "updated_at": "2026-08-15T15:00:00Z",
            },
            {
                "uuid": "0198ad01-b200-7000-8000-000000000101",
                "front_text": "пока",
                "back_text": "bye",
                "front_lang": "ru",
                "back_lang": "en",
                "updated_at": "2026-08-15T15:00:00Z",
            },
        ]

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.get_deck_cards.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            offset=0,
            limit=50,
        )

    async def test_returns_empty_card_list(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_deck_cards.return_value = []

        response = await client.get(f"/decks/{deck.uuid}/cards")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        deck_service.get_deck_cards.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            offset=0,
            limit=50,
        )

    @pytest.mark.parametrize("optional_current_user", [None], indirect=True)
    async def test_passes_anonymous_viewer_and_custom_pagination(
        self,
        client: AsyncClient,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_deck_cards.return_value = []

        response = await client.get(
            f"/decks/{deck.uuid}/cards",
            params={"offset": 10, "limit": 25},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        deck_service.get_deck_cards.assert_awaited_once_with(
            user_id=None,
            deck_uuid=deck.uuid,
            offset=10,
            limit=25,
        )

    async def test_accepts_maximum_card_limit(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_deck_cards.return_value = []

        response = await client.get(
            f"/decks/{deck.uuid}/cards",
            params={"limit": 500},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        deck_service.get_deck_cards.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            offset=0,
            limit=500,
        )

    @pytest.mark.parametrize(
        ("params", "expected_detail"),
        [
            pytest.param(
                {"offset": -1},
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "offset"],
                    "msg": "Input should be greater than or equal to 0",
                    "input": "-1",
                    "ctx": {"ge": 0},
                },
                id="negative_offset",
            ),
            pytest.param(
                {"limit": 0},
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="limit_below_minimum",
            ),
            pytest.param(
                {"limit": 501},
                {
                    "type": "less_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be less than or equal to 500",
                    "input": "501",
                    "ctx": {"le": 500},
                },
                id="limit_above_maximum",
            ),
        ],
    )
    async def test_rejects_invalid_pagination(
        self,
        client: AsyncClient,
        deck,
        params,
        expected_detail,
        deck_service: AsyncMock,
    ):
        response = await client.get(
            f"/decks/{deck.uuid}/cards",
            params=params,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_deck_cards.assert_not_awaited()

    async def test_returns_404_when_deck_not_found(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_deck_cards.side_effect = DeckNotFoundError()

        response = await client.get(f"/decks/{deck.uuid}/cards")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "code": "DECK_NOT_FOUND",
            "message": "Deck not found",
        }

        deck_service.get_deck_cards.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            offset=0,
            limit=50,
        )

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.get("/decks/not-a-uuid/cards")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "deck_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        deck_service.get_deck_cards.assert_not_awaited()


class TestRemoveCardFromDeck:
    async def test_removes_card_from_deck(
        self,
        client: AsyncClient,
        current_user,
        deck,
        card,
        deck_service: AsyncMock,
    ):
        response = await client.post(f"/decks/{deck.uuid}/cards/remove/{card.uuid}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        deck_service.remove_card_from_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "CARD_NOT_FOUND",
                "Card not found",
                id="card_not_found",
            ),
            pytest.param(
                DeckCardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_CARD_NOT_FOUND",
                "Deck card link not found",
                id="deck_card_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "DECK_PERMISSION_DENIED",
                "Permission denied",
                id="permission_denied",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        card,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        deck_service: AsyncMock,
    ):
        deck_service.remove_card_from_deck.side_effect = service_error

        response = await client.post(f"/decks/{deck.uuid}/cards/remove/{card.uuid}")

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        deck_service.remove_card_from_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
        )

    @pytest.mark.parametrize(
        ("deck_uuid", "card_uuid", "field"),
        [
            pytest.param(
                "not-a-uuid",
                "0198ad01-b200-7000-8000-000000000100",
                "deck_uuid",
                id="invalid_deck_uuid",
            ),
            pytest.param(
                "0198ad01-b200-7000-8000-000000000200",
                "not-a-uuid",
                "card_uuid",
                id="invalid_card_uuid",
            ),
        ],
    )
    async def test_rejects_invalid_uuid(
        self,
        client: AsyncClient,
        deck_uuid,
        card_uuid,
        field,
        deck_service: AsyncMock,
    ):
        response = await client.post(f"/decks/{deck_uuid}/cards/remove/{card_uuid}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", field],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        deck_service.remove_card_from_deck.assert_not_awaited()


class TestReorderDeckCards:
    async def test_reorders_card(
        self,
        client: AsyncClient,
        current_user,
        deck,
        card,
        deck_service: AsyncMock,
    ):
        payload = {
            "card_uuid": str(card.uuid),
            "to_position": 3,
        }

        response = await client.post(
            f"/decks/{deck.uuid}/cards/reorder",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None

        deck_service.reorder_cards.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
            to_position=3,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "CARD_NOT_FOUND",
                "Card not found",
                id="card_not_found",
            ),
            pytest.param(
                DeckCardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_CARD_NOT_FOUND",
                "Deck card link not found",
                id="deck_card_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "DECK_PERMISSION_DENIED",
                "Permission denied",
                id="permission_denied",
            ),
            pytest.param(
                InvalidDeckCardPositionError(),
                status.HTTP_409_CONFLICT,
                "INVALID_DECK_CARD_POSITION",
                "Invalid card position in deck",
                id="invalid_position",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        card,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        deck_service: AsyncMock,
    ):
        payload = {
            "card_uuid": str(card.uuid),
            "to_position": 3,
        }
        deck_service.reorder_cards.side_effect = service_error

        response = await client.post(
            f"/decks/{deck.uuid}/cards/reorder",
            json=payload,
        )

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        deck_service.reorder_cards.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
            to_position=3,
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {
                    "card_uuid": "0198ad01-b200-7000-8000-000000000100",
                    "to_position": 0,
                },
                {
                    "type": "greater_than_equal",
                    "loc": ["body", "to_position"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": 0,
                    "ctx": {"ge": 1},
                },
                id="position_below_minimum",
            ),
            pytest.param(
                {
                    "card_uuid": "not-a-uuid",
                    "to_position": 1,
                },
                {
                    "type": "uuid_parsing",
                    "loc": ["body", "card_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                },
                id="invalid_card_uuid",
            ),
        ],
    )
    async def test_rejects_invalid_payload(
        self,
        client: AsyncClient,
        deck,
        payload,
        expected_detail,
        deck_service: AsyncMock,
    ):
        response = await client.post(
            f"/decks/{deck.uuid}/cards/reorder",
            json=payload,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.reorder_cards.assert_not_awaited()

    @pytest.mark.parametrize(
        ("payload", "field"),
        [
            pytest.param({"to_position": 1}, "card_uuid", id="card_uuid_missing"),
            pytest.param(
                {"card_uuid": "0198ad01-b200-7000-8000-000000000100"},
                "to_position",
                id="to_position_missing",
            ),
        ],
    )
    async def test_rejects_missing_field(
        self,
        client: AsyncClient,
        deck,
        payload,
        field,
        deck_service: AsyncMock,
    ):
        response = await client.post(
            f"/decks/{deck.uuid}/cards/reorder",
            json=payload,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "missing",
                    "loc": ["body", field],
                    "msg": "Field required",
                    "input": payload,
                }
            ],
        }

        deck_service.reorder_cards.assert_not_awaited()


class TestLoadCardsToDeck:
    async def test_imports_cards(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        payload = {
            "cards": [
                {
                    "front_text": "привет",
                    "back_text": "hello",
                    "front_lang": "ru",
                    "back_lang": "en",
                },
                {
                    "front_text": "пока",
                    "back_text": "bye",
                    "front_lang": "ru",
                    "back_lang": "en",
                },
            ]
        }
        deck_service.load_cards_to_deck.return_value = {
            "imported_count": 2,
            "cards": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000100",
                    "position": 1,
                },
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000101",
                    "position": 2,
                },
            ],
        }

        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json=payload,
        )

        expected = {
            "imported_count": 2,
            "cards": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000100",
                    "position": 1,
                },
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000101",
                    "position": 2,
                },
            ],
        }

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == expected

        deck_service.load_cards_to_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            cards=[
                CreateCardRequest(
                    front_text="привет",
                    back_text="hello",
                    front_lang="ru",
                    back_lang="en",
                ),
                CreateCardRequest(
                    front_text="пока",
                    back_text="bye",
                    front_lang="ru",
                    back_lang="en",
                ),
            ],
            user_id=current_user.id,
        )

    async def test_normalizes_all_card_fields(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        payload = {
            "cards": [
                {
                    "front_text": "  ДОБРОЕ УТРО  ",
                    "back_text": "  GOOD MORNING  ",
                    "front_lang": "  RU  ",
                    "back_lang": "  EN  ",
                }
            ]
        }
        deck_service.load_cards_to_deck.return_value = {
            "imported_count": 1,
            "cards": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000100",
                    "position": 1,
                }
            ],
        }

        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json=payload,
        )

        expected = {
            "imported_count": 1,
            "cards": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000100",
                    "position": 1,
                }
            ],
        }

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == expected

        deck_service.load_cards_to_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            cards=[
                CreateCardRequest(
                    front_text="ДОБРОЕ УТРО",
                    back_text="GOOD MORNING",
                    front_lang="ru",
                    back_lang="en",
                )
            ],
            user_id=current_user.id,
        )

    async def test_accepts_maximum_number_of_cards(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        card_payload = {
            "front_text": "a",
            "back_text": "b",
            "front_lang": "ru",
            "back_lang": "en",
        }
        payload = {"cards": [card_payload] * 500}
        imported_cards = [
            {
                "uuid": f"0198ad01-b200-7000-8000-{position:012d}",
                "position": position,
            }
            for position in range(1, 501)
        ]
        deck_service.load_cards_to_deck.return_value = {
            "imported_count": 500,
            "cards": imported_cards,
        }

        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json=payload,
        )

        expected = {
            "imported_count": 500,
            "cards": imported_cards,
        }

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == expected

        deck_service.load_cards_to_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            cards=[CreateCardRequest(**card_payload)] * 500,
            user_id=current_user.id,
        )

    @pytest.mark.parametrize(
        ("card_payload", "expected_detail"),
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
                    "loc": ["body", "cards", 0, "front_text"],
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
                    "loc": ["body", "cards", 0, "back_text"],
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
                    "loc": ["body", "cards", 0, "front_lang"],
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
                    "loc": ["body", "cards", 0, "back_lang"],
                    "msg": "String should have at most 3 characters",
                    "input": "engl",
                    "ctx": {"max_length": 3},
                },
                id="back_lang_too_long",
            ),
        ],
    )
    async def test_rejects_invalid_card(
        self,
        client: AsyncClient,
        deck,
        card_payload,
        expected_detail,
        deck_service: AsyncMock,
    ):
        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json={"cards": [card_payload]},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.load_cards_to_deck.assert_not_awaited()

    @pytest.mark.parametrize(
        ("payload", "expected_details"),
        [
            pytest.param(
                {},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "cards"],
                        "msg": "Field required",
                        "input": {},
                    }
                ],
                id="cards_missing",
            ),
            pytest.param(
                {
                    "cards": [
                        {
                            "back_text": "hello",
                            "front_lang": "ru",
                            "back_lang": "en",
                        }
                    ]
                },
                [
                    {
                        "type": "missing",
                        "loc": ["body", "cards", 0, "front_text"],
                        "msg": "Field required",
                        "input": {
                            "back_text": "hello",
                            "front_lang": "ru",
                            "back_lang": "en",
                        },
                    }
                ],
                id="front_text_missing",
            ),
            pytest.param(
                {
                    "cards": [
                        {
                            "front_text": "привет",
                            "front_lang": "ru",
                            "back_lang": "en",
                        }
                    ]
                },
                [
                    {
                        "type": "missing",
                        "loc": ["body", "cards", 0, "back_text"],
                        "msg": "Field required",
                        "input": {
                            "front_text": "привет",
                            "front_lang": "ru",
                            "back_lang": "en",
                        },
                    }
                ],
                id="back_text_missing",
            ),
        ],
    )
    async def test_rejects_missing_fields(
        self,
        client: AsyncClient,
        deck,
        payload,
        expected_details,
        deck_service: AsyncMock,
    ):
        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json=payload,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": expected_details,
        }

        deck_service.load_cards_to_deck.assert_not_awaited()

    async def test_rejects_empty_card_list(
        self,
        client: AsyncClient,
        deck,
        deck_service: AsyncMock,
    ):
        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json={"cards": []},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "too_short",
                    "loc": ["body", "cards"],
                    "msg": "List should have at least 1 item after validation, not 0",
                    "input": [],
                    "ctx": {"field_type": "List", "min_length": 1, "actual_length": 0},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        deck_service.load_cards_to_deck.assert_not_awaited()

    async def test_rejects_more_than_500_cards(
        self,
        client: AsyncClient,
        deck,
        deck_service: AsyncMock,
    ):
        card_payload = {
            "front_text": "a",
            "back_text": "b",
            "front_lang": "ru",
            "back_lang": "en",
        }
        cards = [card_payload] * 501

        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json={"cards": cards},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "too_long",
                    "loc": ["body", "cards"],
                    "msg": (
                        "List should have at most 500 items after validation, not 501"
                    ),
                    "input": cards,
                    "ctx": {
                        "field_type": "List",
                        "max_length": 500,
                        "actual_length": 501,
                    },
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        deck_service.load_cards_to_deck.assert_not_awaited()

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                DeckSizeLimitExceededError(limit=5000, current=5000, requested=1),
                status.HTTP_409_CONFLICT,
                "DECK_SIZE_LIMIT_EXCEEDED",
                "Deck size limit exceeded: deck has 5000/5000 cards, "
                "cannot add 1 more (only 0 slots left)",
                id="deck_size_limit",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        deck_service: AsyncMock,
    ):
        payload = {
            "cards": [
                {
                    "front_text": "привет",
                    "back_text": "hello",
                    "front_lang": "ru",
                    "back_lang": "en",
                }
            ]
        }
        deck_service.load_cards_to_deck.side_effect = service_error

        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json=payload,
        )

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        deck_service.load_cards_to_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            cards=[CreateCardRequest(**payload["cards"][0])],
            user_id=current_user.id,
        )


class TestAddCardToDeck:
    async def test_adds_card_to_deck(
        self,
        client: AsyncClient,
        current_user,
        deck,
        card,
        deck_service: AsyncMock,
    ):
        deck_card = make_deck_card()
        deck_service.add_card_to_deck.return_value = deck_card

        response = await client.post(f"/decks/{deck.uuid}/cards/{card.uuid}")

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000300",
            "position": 1,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.add_card_to_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
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
                "DECK_PERMISSION_DENIED",
                "Permission denied",
                id="permission_denied",
            ),
            pytest.param(
                DeckCardAlreadyExistsError(),
                status.HTTP_409_CONFLICT,
                "DECK_CARD_ALREADY_EXISTS",
                "Card already exists in this deck",
                id="card_already_in_deck",
            ),
            pytest.param(
                DeckSizeLimitExceededError(limit=5000, current=5000, requested=1),
                status.HTTP_409_CONFLICT,
                "DECK_SIZE_LIMIT_EXCEEDED",
                "Deck size limit exceeded: deck has 5000/5000 cards, "
                "cannot add 1 more (only 0 slots left)",
                id="deck_size_limit",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        card,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        deck_service: AsyncMock,
    ):
        deck_service.add_card_to_deck.side_effect = service_error

        response = await client.post(f"/decks/{deck.uuid}/cards/{card.uuid}")

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        deck_service.add_card_to_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
        )

    @pytest.mark.parametrize(
        ("deck_uuid", "card_uuid", "field"),
        [
            pytest.param(
                "not-a-uuid",
                "0198ad01-b200-7000-8000-000000000100",
                "deck_uuid",
                id="invalid_deck_uuid",
            ),
            pytest.param(
                "0198ad01-b200-7000-8000-000000000200",
                "not-a-uuid",
                "card_uuid",
                id="invalid_card_uuid",
            ),
        ],
    )
    async def test_rejects_invalid_uuid(
        self,
        client: AsyncClient,
        deck_uuid,
        card_uuid,
        field,
        deck_service: AsyncMock,
    ):
        response = await client.post(f"/decks/{deck_uuid}/cards/{card_uuid}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", field],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        deck_service.add_card_to_deck.assert_not_awaited()


class TestSetFavourite:
    async def test_sets_deck_as_favourite_by_default(
        self,
        client: AsyncClient,
        current_user,
        deck,
        user_deck_service: AsyncMock,
    ):
        user_deck_service.set_favourite_deck.return_value = make_user_deck(
            is_favourite=True
        )

        response = await client.patch(f"/decks/{deck.uuid}/set-favourite")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is True

        user_deck_service.set_favourite_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            value=True,
        )

    async def test_removes_deck_from_favourites(
        self,
        client: AsyncClient,
        current_user,
        deck,
        user_deck_service: AsyncMock,
    ):
        user_deck_service.set_favourite_deck.return_value = make_user_deck(
            is_favourite=False
        )

        response = await client.patch(
            f"/decks/{deck.uuid}/set-favourite",
            params={"value": False},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is False

        user_deck_service.set_favourite_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            value=False,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CannotFavouriteUnsavedDeckError(),
                status.HTTP_409_CONFLICT,
                "CANNOT_FAVOURITE_UNSAVED_DECK",
                "Save the deck before adding it to favourites",
                id="deck_not_saved",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        user_deck_service: AsyncMock,
    ):
        user_deck_service.set_favourite_deck.side_effect = service_error

        response = await client.patch(f"/decks/{deck.uuid}/set-favourite")

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        user_deck_service.set_favourite_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
            value=True,
        )

    async def test_rejects_invalid_boolean_value(
        self,
        client: AsyncClient,
        deck,
        user_deck_service: AsyncMock,
    ):
        response = await client.patch(
            f"/decks/{deck.uuid}/set-favourite",
            params={"value": "not-a-bool"},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "bool_parsing",
                    "loc": ["query", "value"],
                    "msg": (
                        "Input should be a valid boolean, unable to interpret input"
                    ),
                    "input": "not-a-bool",
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        user_deck_service.set_favourite_deck.assert_not_awaited()

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        user_deck_service: AsyncMock,
    ):
        response = await client.patch("/decks/not-a-uuid/set-favourite")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "deck_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        user_deck_service.set_favourite_deck.assert_not_awaited()


class TestSaveDeck:
    async def test_saves_deck(
        self,
        client: AsyncClient,
        current_user,
        deck,
        user_deck_service: AsyncMock,
    ):
        response = await client.post(f"/decks/{deck.uuid}/save")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b""

        user_deck_service.save_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CannotSaveOwnDeckError(),
                status.HTTP_409_CONFLICT,
                "CANNOT_SAVE_OWN_DECK",
                "You cannot save your own deck",
                id="own_deck",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        user_deck_service: AsyncMock,
    ):
        user_deck_service.save_deck.side_effect = service_error

        response = await client.post(f"/decks/{deck.uuid}/save")

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        user_deck_service.save_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
        )

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        user_deck_service: AsyncMock,
    ):
        response = await client.post("/decks/not-a-uuid/save")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "deck_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        user_deck_service.save_deck.assert_not_awaited()


class TestUnsaveDeck:
    async def test_unsaves_deck(
        self,
        client: AsyncClient,
        current_user,
        deck,
        user_deck_service: AsyncMock,
    ):
        response = await client.post(f"/decks/{deck.uuid}/unsave")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b""

        user_deck_service.unsave_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "DECK_NOT_FOUND",
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CannotSaveOwnDeckError(),
                status.HTTP_409_CONFLICT,
                "CANNOT_SAVE_OWN_DECK",
                "You cannot save your own deck",
                id="own_deck",
            ),
            pytest.param(
                DeckIsNotSavedError(),
                status.HTTP_409_CONFLICT,
                "DECK_IS_NOT_SAVED",
                "Deck is not saved",
                id="deck_not_saved",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        deck,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        user_deck_service: AsyncMock,
    ):
        user_deck_service.unsave_deck.side_effect = service_error

        response = await client.post(f"/decks/{deck.uuid}/unsave")

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        user_deck_service.unsave_deck.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=deck.uuid,
        )

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        user_deck_service: AsyncMock,
    ):
        response = await client.post("/decks/not-a-uuid/unsave")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "deck_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        user_deck_service.unsave_deck.assert_not_awaited()


class TestGetArchives:
    async def test_lists_only_service_returned_archive_offers(
        self, client: AsyncClient, current_user, deck_service: AsyncMock,
    ):
        deck_service.get_archives_for_user.return_value = [{
            "uuid": UUID("0198ad01-b200-7000-8000-000000000201"),
            "title": "Archived deck",
            "expires_at": datetime(2030, 10, 1, tzinfo=UTC),
            "preserved_deck_uuid": None,
        }]

        response = await client.get("/decks/archives")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [{
            "uuid": "0198ad01-b200-7000-8000-000000000201",
            "title": "Archived deck",
            "expires_at": "2030-10-01T00:00:00Z",
            "preserved_deck_uuid": None,
        }]
        deck_service.get_archives_for_user.assert_awaited_once_with(current_user.id)


class TestGetArchiveDeck:
    async def test_returns_archive_details(
        self, client: AsyncClient, current_user, deck_service: AsyncMock,
    ):
        archive_uuid = UUID("0198ad01-b200-7000-8000-000000000201")
        deck_service.get_archive_deck.return_value = {
            "uuid": archive_uuid,
            "title": "Archived deck",
            "description": "Archived description",
            "words_count": 2,
            "archived_at": datetime(2026, 9, 1, tzinfo=UTC),
            "expires_at": datetime(2030, 10, 1, tzinfo=UTC),
            "archive_reason": "deleted",
            "source_deck_uuid_snapshot": UUID(
                "0198ad01-b200-7000-8000-000000000202"
            ),
            "preserved_deck_uuid": None,
        }

        response = await client.get(f"/decks/archives/{archive_uuid}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "uuid": "0198ad01-b200-7000-8000-000000000201",
            "title": "Archived deck",
            "description": "Archived description",
            "words_count": 2,
            "archived_at": "2026-09-01T00:00:00Z",
            "expires_at": "2030-10-01T00:00:00Z",
            "archive_reason": "deleted",
            "source_deck_uuid_snapshot": "0198ad01-b200-7000-8000-000000000202",
            "preserved_deck_uuid": None,
        }
        deck_service.get_archive_deck.assert_awaited_once_with(
            deck_uuid=archive_uuid, user_id=current_user.id,
        )

    @pytest.mark.parametrize(
        ("suffix", "method_name"),
        [("", "get_archive_deck"), ("/cards", "get_archive_cards")],
    )
    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            (DeckNotArchivedError(), 409, "DECK_NOT_ARCHIVED", "Deck is not archived"),
            (DeckNotFoundError(), 404, "DECK_NOT_FOUND", "Deck not found"),
            (PermissionDeniedError(), 403, "DECK_PERMISSION_DENIED", "Permission denied"),
            (ArchiveExpiredError("Archive preservation period has expired"),
             410, "ARCHIVE_EXPIRED", "Archive preservation period has expired"),
        ],
    )
    async def test_returns_archive_access_error(
        self, client: AsyncClient, current_user, deck_service: AsyncMock,
        suffix, method_name, service_error, expected_status,
        expected_code, expected_message,
    ):
        service_method = getattr(deck_service, method_name)
        service_method.side_effect = service_error

        response = await client.get(
            f"/decks/archives/0198ad01-b200-7000-8000-000000000201{suffix}"
        )

        assert response.status_code == expected_status
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }
        expected_kwargs = {
            "deck_uuid": UUID("0198ad01-b200-7000-8000-000000000201"),
            "user_id": current_user.id,
        }
        if suffix == "/cards":
            expected_kwargs.update(offset=0, limit=50)
        service_method.assert_awaited_once_with(**expected_kwargs)


class TestGetArchiveCards:
    async def test_returns_card_page(
        self, client: AsyncClient, current_user, deck_service: AsyncMock,
    ):
        archive_uuid = UUID("0198ad01-b200-7000-8000-000000000201")
        deck_service.get_archive_cards.return_value = [{
            "uuid": UUID("0198ad01-b200-7000-8000-000000000203"),
            "front_text": "front",
            "back_text": "back",
            "front_lang": "en",
            "back_lang": "ru",
            "updated_at": datetime(2026, 9, 1, tzinfo=UTC),
        }]

        response = await client.get(
            f"/decks/archives/{archive_uuid}/cards?offset=5&limit=10"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == [{
            "uuid": "0198ad01-b200-7000-8000-000000000203",
            "front_text": "front",
            "back_text": "back",
            "front_lang": "en",
            "back_lang": "ru",
            "updated_at": "2026-09-01T00:00:00Z",
        }]
        deck_service.get_archive_cards.assert_awaited_once_with(
            deck_uuid=archive_uuid,
            user_id=current_user.id,
            offset=5,
            limit=10,
        )

    async def test_rejects_invalid_page_size(
        self, client: AsyncClient, deck_service: AsyncMock,
    ):
        response = await client.get(
            "/decks/archives/0198ad01-b200-7000-8000-000000000201/cards?limit=501"
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [{
                "type": "less_than_equal",
                "loc": ["query", "limit"],
                "msg": "Input should be less than or equal to 500",
                "input": "501",
                "ctx": {"le": 500},
            }],
        }
        deck_service.get_archive_cards.assert_not_awaited()


class TestPreserveArchivedDeck:
    @pytest.mark.parametrize(("already_preserved", "copy_deleted"), [
        (False, False), (True, False), (True, True),
    ])
    async def test_returns_private_copy_uuid(
        self, client: AsyncClient, current_user, deck_service: AsyncMock,
        already_preserved, copy_deleted,
    ):
        archive_uuid = UUID("0198ad01-b200-7000-8000-000000000201")
        deck_service.preserve_archived_deck.return_value = SimpleNamespace(
            deck_uuid=UUID("0198ad01-b200-7000-8000-000000000202"),
            already_preserved=already_preserved,
            copy_deleted=copy_deleted,
        )

        response = await client.post(f"/decks/{archive_uuid}/preserve")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "uuid": "0198ad01-b200-7000-8000-000000000202",
            "already_preserved": already_preserved,
            "copy_deleted": copy_deleted,
        }
        deck_service.preserve_archived_deck.assert_awaited_once_with(
            archive_deck_uuid=archive_uuid, user_id=current_user.id,
        )

    async def test_returns_gone_when_archive_expired(
        self, client: AsyncClient, deck_service: AsyncMock,
    ):
        deck_service.preserve_archived_deck.side_effect = ArchiveExpiredError(
            "Archive preservation period has expired"
        )

        response = await client.post(
            "/decks/0198ad01-b200-7000-8000-000000000201/preserve"
        )

        assert response.status_code == status.HTTP_410_GONE
        assert response.json() == {
            "code": "ARCHIVE_EXPIRED",
            "message": "Archive preservation period has expired",
        }


class TestDeckAuthentication:
    @pytest.mark.parametrize(("method", "suffix", "payload"), [
        ("POST", "create", {"title": "English"}),
        ("PATCH", "0198ad01-b200-7000-8000-000000000200", {}),
        ("DELETE", "0198ad01-b200-7000-8000-000000000200", None),
        ("POST", "0198ad01-b200-7000-8000-000000000200/preserve", None),
        ("POST", "0198ad01-b200-7000-8000-000000000200/cards/remove/0198ad01-b200-7000-8000-000000000100", None),
        ("POST", "0198ad01-b200-7000-8000-000000000200/cards/reorder",
         {"card_uuid": "0198ad01-b200-7000-8000-000000000100", "to_position": 1}),
        ("POST", "0198ad01-b200-7000-8000-000000000200/cards/import",
         {"cards": [{"front_text": "привет", "back_text": "hello"}]}),
        ("POST", "0198ad01-b200-7000-8000-000000000200/cards/0198ad01-b200-7000-8000-000000000100", None),
        ("PATCH", "0198ad01-b200-7000-8000-000000000200/set-favourite", None),
        ("POST", "0198ad01-b200-7000-8000-000000000200/save", None),
        ("POST", "0198ad01-b200-7000-8000-000000000200/unsave", None),
        ("GET", "archives", None),
        ("GET", "archives/0198ad01-b200-7000-8000-000000000201", None),
        ("GET", "archives/0198ad01-b200-7000-8000-000000000201/cards", None),
    ])
    async def test_returns_401_without_calling_deck_services(
        self, app, client, deck_service, user_deck_service, monkeypatch,
        method, suffix, payload,
    ):
        async def reject_unauthenticated_user():
            raise AccessTokenNotFoundError()

        monkeypatch.setitem(
            app.dependency_overrides, get_current_user, reject_unauthenticated_user,
        )

        response = await client.request(method, f"/decks/{suffix}", json=payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {
            "code": "ACCESS_TOKEN_NOT_FOUND",
            "message": "Not authorized",
        }
        assert deck_service.mock_calls == []
        assert user_deck_service.mock_calls == []
