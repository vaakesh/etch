from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient

from app.cards.errors import CardNotFoundError
from app.cards.schemas import CreateCardRequest
from app.decks.errors import (
    CannotSaveOwnDeckError,
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckIsNotFavouriteError,
    DeckIsNotSavedError,
    DeckNotFoundError,
    InvalidDeckCardPositionError,
    PermissionDeniedError,
)
from app.decks.schemas import CreateDeckRequest, UpdateDeckRequest
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
        deck_service.get_by_uuid.return_value = deck

        response = await client.get(f"/decks/{deck.uuid}")

        expected = {
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
            "title": "Test deck",
            "description": "Test deck description",
            "words_count": 10,
            "is_public": True,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.get_by_uuid.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            current_user_id=current_user.id,
        )

    @pytest.mark.parametrize("optional_current_user", [None], indirect=True)
    async def test_returns_public_deck_for_anonymous_viewer(
        self,
        client: AsyncClient,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_by_uuid.return_value = deck

        response = await client.get(f"/decks/{deck.uuid}")

        expected = {
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
            "title": "Test deck",
            "description": "Test deck description",
            "words_count": 10,
            "is_public": True,
            "saves_count": 5,
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.get_by_uuid.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            current_user_id=None,
        )

    async def test_returns_404_when_deck_not_found(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        deck_service.get_by_uuid.side_effect = DeckNotFoundError()

        response = await client.get("/decks/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"message": "Deck not found"}

        deck_service.get_by_uuid.assert_awaited_once()

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.get("/decks/not-a-uuid")

        expected = {
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

        deck_service.get_by_uuid.assert_not_awaited()


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
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
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
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
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
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
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
        )

    @pytest.mark.parametrize(
        ("title", "description"),
        [
            pytest.param("abc", "", id="minimum_title_and_empty_description"),
            pytest.param(
                "a" * 50,
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
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
            "title": title,
            "description": description,
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
        assert response.json() == {"message": "Deck already exists"}

        deck_service.create_deck.assert_awaited_once_with(
            CreateDeckRequest(**payload),
            user_id=current_user.id,
            user_uuid=current_user.uuid,
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
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
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
            user_uuid=current_user.uuid,
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
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
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
            user_uuid=current_user.uuid,
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
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
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
            user_uuid=current_user.uuid,
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
            "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "owner_uuid": "12345678-1234-5678-1234-567812345678",
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
            user_uuid=current_user.uuid,
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
                {"description": "d" * 3001},
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
        deck,
        payload,
        expected_detail,
        deck_service: AsyncMock,
    ):
        response = await client.patch(f"/decks/{deck.uuid}", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
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
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "Permission denied",
                id="permission_denied",
            ),
            pytest.param(
                DeckAlreadyExistsError(),
                status.HTTP_409_CONFLICT,
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
        expected_message,
        deck_service: AsyncMock,
    ):
        payload = {"title": "Updated deck"}
        deck_service.update_deck.side_effect = service_error

        response = await client.patch(f"/decks/{deck.uuid}", json=payload)

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}

        deck_service.update_deck.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
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
            user_uuid=current_user.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
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
        service_error,
        expected_status,
        expected_message,
        deck_service: AsyncMock,
    ):
        deck_service.delete_deck.side_effect = service_error

        response = await client.delete(f"/decks/{deck.uuid}")

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}

        deck_service.delete_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            user_id=current_user.id,
            user_uuid=current_user.uuid,
        )

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.delete("/decks/not-a-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
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
            uuid=UUID("11111111-1111-1111-1111-111111111111"),
            front_text="пока",
            back_text="bye",
            front_lang="ru",
            back_lang="en",
        )
        deck_service.get_deck_cards.return_value = [first_card, second_card]

        response = await client.get(f"/decks/{deck.uuid}/cards")

        expected = [
            {
                "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "front_text": "привет",
                "back_text": "hello",
                "front_lang": "ru",
                "back_lang": "en",
                "updated_at": "2026-08-15T15:00:00Z",
            },
            {
                "uuid": "11111111-1111-1111-1111-111111111111",
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
                {"limit": 51},
                {
                    "type": "less_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be less than or equal to 50",
                    "input": "51",
                    "ctx": {"le": 50},
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
        assert response.json() == {"message": "Deck not found"}

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


class TestGetCardInDeck:
    async def test_returns_card_for_authenticated_viewer(
        self,
        client: AsyncClient,
        current_user,
        deck,
        card,
        card_service: AsyncMock,
    ):
        card_service.get_card_in_deck.return_value = card

        response = await client.get(f"/decks/{deck.uuid}/cards/{card.uuid}")

        expected = {
            "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "front_text": "привет",
            "back_text": "hello",
            "front_lang": "ru",
            "back_lang": "en",
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.get_card_in_deck.assert_awaited_once_with(
            card_uuid=card.uuid,
            deck_uuid=deck.uuid,
            viewer_id=current_user.id,
        )

    @pytest.mark.parametrize("optional_current_user", [None], indirect=True)
    async def test_returns_public_card_for_anonymous_viewer(
        self,
        client: AsyncClient,
        deck,
        card,
        card_service: AsyncMock,
    ):
        card_service.get_card_in_deck.return_value = card

        response = await client.get(f"/decks/{deck.uuid}/cards/{card.uuid}")

        expected = {
            "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "front_text": "привет",
            "back_text": "hello",
            "front_lang": "ru",
            "back_lang": "en",
            "updated_at": "2026-08-15T15:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        card_service.get_card_in_deck.assert_awaited_once_with(
            card_uuid=card.uuid,
            deck_uuid=deck.uuid,
            viewer_id=None,
        )

    async def test_returns_404_when_card_not_found(
        self,
        client: AsyncClient,
        current_user,
        deck,
        card,
        card_service: AsyncMock,
    ):
        card_service.get_card_in_deck.side_effect = CardNotFoundError()

        response = await client.get(f"/decks/{deck.uuid}/cards/{card.uuid}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"message": "Card not found"}

        card_service.get_card_in_deck.assert_awaited_once_with(
            card_uuid=card.uuid,
            deck_uuid=deck.uuid,
            viewer_id=current_user.id,
        )

    @pytest.mark.parametrize(
        ("deck_uuid", "card_uuid", "field"),
        [
            pytest.param(
                "not-a-uuid",
                "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "deck_uuid",
                id="invalid_deck_uuid",
            ),
            pytest.param(
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
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
        card_service: AsyncMock,
    ):
        response = await client.get(f"/decks/{deck_uuid}/cards/{card_uuid}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
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

        card_service.get_card_in_deck.assert_not_awaited()


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
            user_uuid=current_user.uuid,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Card not found",
                id="card_not_found",
            ),
            pytest.param(
                DeckCardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck card link not found",
                id="deck_card_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
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
        expected_message,
        deck_service: AsyncMock,
    ):
        deck_service.remove_card_from_deck.side_effect = service_error

        response = await client.post(f"/decks/{deck.uuid}/cards/remove/{card.uuid}")

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}

        deck_service.remove_card_from_deck.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
        )

    @pytest.mark.parametrize(
        ("deck_uuid", "card_uuid", "field"),
        [
            pytest.param(
                "not-a-uuid",
                "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "deck_uuid",
                id="invalid_deck_uuid",
            ),
            pytest.param(
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
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
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Card not found",
                id="card_not_found",
            ),
            pytest.param(
                DeckCardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck card link not found",
                id="deck_card_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "Permission denied",
                id="permission_denied",
            ),
            pytest.param(
                InvalidDeckCardPositionError(),
                status.HTTP_409_CONFLICT,
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
        assert response.json() == {"message": expected_message}

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
                    "card_uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
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
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.reorder_cards.assert_not_awaited()

    @pytest.mark.parametrize(
        ("payload", "field"),
        [
            pytest.param({"to_position": 1}, "card_uuid", id="card_uuid_missing"),
            pytest.param(
                {"card_uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
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
                    "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "position": 1,
                },
                {
                    "uuid": "11111111-1111-1111-1111-111111111111",
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
                    "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "position": 1,
                },
                {
                    "uuid": "11111111-1111-1111-1111-111111111111",
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
            user_uuid=current_user.uuid,
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
                    "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
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
                    "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
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
                    front_text="доброе утро",
                    back_text="good morning",
                    front_lang="ru",
                    back_lang="en",
                )
            ],
            user_id=current_user.id,
            user_uuid=current_user.uuid,
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
        deck_service.load_cards_to_deck.return_value = {
            "imported_count": 500,
            "cards": [],
        }

        response = await client.post(
            f"/decks/{deck.uuid}/cards/import",
            json=payload,
        )

        expected = {
            "imported_count": 500,
            "cards": [],
        }

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == expected

        deck_service.load_cards_to_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            cards=[CreateCardRequest(**card_payload)] * 500,
            user_id=current_user.id,
            user_uuid=current_user.uuid,
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
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
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
        service_error,
        expected_status,
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
        assert response.json() == {"message": expected_message}

        deck_service.load_cards_to_deck.assert_awaited_once_with(
            deck_uuid=deck.uuid,
            cards=[CreateCardRequest(**payload["cards"][0])],
            user_id=current_user.id,
            user_uuid=current_user.uuid,
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
            "uuid": "cccccccc-cccc-cccc-cccc-cccccccccccc",
            "position": 1,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.add_card_to_deck.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CardNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Card not found",
                id="card_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "Permission denied",
                id="permission_denied",
            ),
            pytest.param(
                DeckCardAlreadyExistsError(),
                status.HTTP_409_CONFLICT,
                "Card already exists in this deck",
                id="card_already_in_deck",
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
        expected_message,
        deck_service: AsyncMock,
    ):
        deck_service.add_card_to_deck.side_effect = service_error

        response = await client.post(f"/decks/{deck.uuid}/cards/{card.uuid}")

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}

        deck_service.add_card_to_deck.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            deck_uuid=deck.uuid,
            card_uuid=card.uuid,
        )

    @pytest.mark.parametrize(
        ("deck_uuid", "card_uuid", "field"),
        [
            pytest.param(
                "not-a-uuid",
                "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "deck_uuid",
                id="invalid_deck_uuid",
            ),
            pytest.param(
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
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
            user_uuid=current_user.uuid,
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
            user_uuid=current_user.uuid,
            deck_uuid=deck.uuid,
            value=False,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                DeckIsNotFavouriteError(),
                status.HTTP_409_CONFLICT,
                "Deck is not in favourites",
                id="deck_not_favourite",
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
        expected_message,
        user_deck_service: AsyncMock,
    ):
        user_deck_service.set_favourite_deck.side_effect = service_error

        response = await client.patch(f"/decks/{deck.uuid}/set-favourite")

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}

        user_deck_service.set_favourite_deck.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
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
            user_uuid=current_user.uuid,
            deck_uuid=deck.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CannotSaveOwnDeckError(),
                status.HTTP_409_CONFLICT,
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
        expected_message,
        user_deck_service: AsyncMock,
    ):
        user_deck_service.save_deck.side_effect = service_error

        response = await client.post(f"/decks/{deck.uuid}/save")

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}

        user_deck_service.save_deck.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
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
            user_uuid=current_user.uuid,
            deck_uuid=deck.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                CannotSaveOwnDeckError(),
                status.HTTP_409_CONFLICT,
                "You cannot save your own deck",
                id="own_deck",
            ),
            pytest.param(
                DeckIsNotSavedError(),
                status.HTTP_409_CONFLICT,
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
        expected_message,
        user_deck_service: AsyncMock,
    ):
        user_deck_service.unsave_deck.side_effect = service_error

        response = await client.post(f"/decks/{deck.uuid}/unsave")

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}

        user_deck_service.unsave_deck.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
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
