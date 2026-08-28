from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient

from app.decks.errors import (
    DeckIsEmptyError,
    DeckNotFoundError,
    UserDeckNotFoundError,
)
from app.training_sessions.errors import (
    TrainingSessionAlreadyFinishedError,
    TrainingSessionNotFoundError,
)


class TestGetHomeDashboard:
    async def test_returns_home_dashboard(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_home_dashboard.return_value = {
            "decks": [
                {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": "12345678-1234-5678-1234-567812345678",
                    "title": "Test deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "user_accuracy": 75,
                    "updated_at": "2026-08-15T15:00:00Z",
                }
            ],
            "progress": {
                "user_words_explored": 42,
                "user_weekly_accuracy": 80,
                "user_current_streak": 5,
                "user_total_study_time": 3600,
            },
            "user_weekly_activity": [
                {"date": "2026-08-14", "percent": 50},
                {"date": "2026-08-15", "percent": 100},
            ],
        }

        response = await client.get("/bff/home")

        expected = {
            "decks": [
                {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": "12345678-1234-5678-1234-567812345678",
                    "title": "Test deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "user_accuracy": 75,
                    "updated_at": "2026-08-15T15:00:00Z",
                }
            ],
            "progress": {
                "user_words_explored": 42,
                "user_weekly_accuracy": 80,
                "user_current_streak": 5,
                "user_total_study_time": 3600,
            },
            "user_weekly_activity": [
                {"date": "2026-08-14", "percent": 50},
                {"date": "2026-08-15", "percent": 100},
            ],
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_home_dashboard.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
        )

    async def test_returns_empty_home_collections(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_home_dashboard.return_value = {
            "decks": [],
            "progress": {
                "user_words_explored": 0,
                "user_weekly_accuracy": 0,
                "user_current_streak": 0,
                "user_total_study_time": 0,
            },
            "user_weekly_activity": [],
        }

        response = await client.get("/bff/home")

        expected = {
            "decks": [],
            "progress": {
                "user_words_explored": 0,
                "user_weekly_accuracy": 0,
                "user_current_streak": 0,
                "user_total_study_time": 0,
            },
            "user_weekly_activity": [],
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_home_dashboard.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
        )


class TestGetCatalogPage:
    async def test_returns_catalog_with_and_without_viewer_state(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_catalog_page.return_value = [
            {
                "deck": {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": "12345678-1234-5678-1234-567812345678",
                    "title": "Saved deck",
                    "description": "Saved description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                },
                "viewer_state": {
                    "sessions_count": 2,
                    "correct_count": 8,
                    "wrong_count": 2,
                    "accuracy": 80,
                    "last_studied_at": "2026-08-15T16:00:00Z",
                    "is_favourite": True,
                    "is_saved": True,
                },
            },
            {
                "deck": {
                    "uuid": "11111111-1111-1111-1111-111111111111",
                    "owner_uuid": "22222222-2222-2222-2222-222222222222",
                    "title": "New deck",
                    "description": None,
                    "words_count": 3,
                    "is_public": True,
                    "saves_count": 0,
                    "updated_at": None,
                },
                "viewer_state": None,
            },
        ]

        response = await client.get("/bff/catalog")

        expected = [
            {
                "deck": {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": "12345678-1234-5678-1234-567812345678",
                    "title": "Saved deck",
                    "description": "Saved description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                },
                "viewer_state": {
                    "sessions_count": 2,
                    "correct_count": 8,
                    "wrong_count": 2,
                    "accuracy": 80,
                    "last_studied_at": "2026-08-15T16:00:00Z",
                    "is_favourite": True,
                    "is_saved": True,
                },
            },
            {
                "deck": {
                    "uuid": "11111111-1111-1111-1111-111111111111",
                    "owner_uuid": "22222222-2222-2222-2222-222222222222",
                    "title": "New deck",
                    "description": None,
                    "words_count": 3,
                    "is_public": True,
                    "saves_count": 0,
                    "updated_at": None,
                },
                "viewer_state": None,
            },
        ]

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_catalog_page.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=None,
            page=1,
            limit=50,
        )

    async def test_returns_empty_catalog(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_catalog_page.return_value = []

        response = await client.get("/bff/catalog")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        bff_service.get_catalog_page.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=None,
            page=1,
            limit=50,
        )

    @pytest.mark.parametrize(
        ("query", "expected_query", "page", "limit"),
        [
            pytest.param(
                "  VoCaBuLaRy  ",
                "vocabulary",
                2,
                25,
                id="normalizes_query",
            ),
            pytest.param("a", "a", 1, 1, id="minimum_values"),
            pytest.param(
                "a" * 50,
                "a" * 50,
                3,
                100,
                id="maximum_query_and_limit",
            ),
        ],
    )
    async def test_passes_normalized_search_and_pagination(
        self,
        client: AsyncClient,
        current_user,
        query,
        expected_query,
        page,
        limit,
        bff_service: AsyncMock,
    ):
        bff_service.get_catalog_page.return_value = []

        response = await client.get(
            "/bff/catalog",
            params={"q": query, "page": page, "limit": limit},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        bff_service.get_catalog_page.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=expected_query,
            page=page,
            limit=limit,
        )

    @pytest.mark.parametrize(
        ("params", "expected_detail"),
        [
            pytest.param(
                {"q": ""},
                {
                    "type": "string_too_short",
                    "loc": ["query", "q"],
                    "msg": "String should have at least 1 character",
                    "input": "",
                    "ctx": {"min_length": 1},
                },
                id="query_empty",
            ),
            pytest.param(
                {"q": "a" * 51},
                {
                    "type": "string_too_long",
                    "loc": ["query", "q"],
                    "msg": "String should have at most 50 characters",
                    "input": "a" * 51,
                    "ctx": {"max_length": 50},
                },
                id="query_too_long",
            ),
            pytest.param(
                {"page": 0},
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "page"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="page_below_minimum",
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
                {"limit": 101},
                {
                    "type": "less_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be less than or equal to 100",
                    "input": "101",
                    "ctx": {"le": 100},
                },
                id="limit_above_maximum",
            ),
        ],
    )
    async def test_rejects_invalid_query_params(
        self,
        client: AsyncClient,
        params,
        expected_detail,
        bff_service: AsyncMock,
    ):
        response = await client.get("/bff/catalog", params=params)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
        }
        bff_service.get_catalog_page.assert_not_awaited()


class TestGetDecksLibraryPage:
    async def test_returns_decks_library_page(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_decks_library_page.return_value = {
            "items": [
                {
                    "deck": {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "owner_uuid": "12345678-1234-5678-1234-567812345678",
                        "title": "Test deck",
                        "description": "Test deck description",
                        "words_count": 10,
                        "is_public": True,
                        "saves_count": 5,
                        "updated_at": "2026-08-15T15:00:00Z",
                    },
                    "viewer_state": {
                        "sessions_count": 1,
                        "correct_count": 9,
                        "wrong_count": 1,
                        "accuracy": 90,
                        "last_studied_at": None,
                        "is_favourite": False,
                        "is_saved": True,
                    },
                    "preview_cards": [
                        {
                            "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                            "front_text": "привет",
                            "back_text": "hello",
                            "front_lang": "ru",
                            "back_lang": "en",
                            "updated_at": "2026-08-15T15:00:00Z",
                        }
                    ],
                }
            ],
            "next_cursor": "next-deck-cursor",
            "has_more": True,
        }

        response = await client.get("/bff/library/decks")

        expected = {
            "items": [
                {
                    "deck": {
                        "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "owner_uuid": "12345678-1234-5678-1234-567812345678",
                        "title": "Test deck",
                        "description": "Test deck description",
                        "words_count": 10,
                        "is_public": True,
                        "saves_count": 5,
                        "updated_at": "2026-08-15T15:00:00Z",
                    },
                    "viewer_state": {
                        "sessions_count": 1,
                        "correct_count": 9,
                        "wrong_count": 1,
                        "accuracy": 90,
                        "last_studied_at": None,
                        "is_favourite": False,
                        "is_saved": True,
                    },
                    "preview_cards": [
                        {
                            "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                            "front_text": "привет",
                            "back_text": "hello",
                            "front_lang": "ru",
                            "back_lang": "en",
                            "updated_at": "2026-08-15T15:00:00Z",
                        }
                    ],
                }
            ],
            "next_cursor": "next-deck-cursor",
            "has_more": True,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_decks_library_page.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            search_query=None,
            is_favourite=False,
            cursor=None,
            limit=50,
        )

    async def test_returns_empty_decks_library_page(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_decks_library_page.return_value = {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        response = await client.get("/bff/library/decks")

        expected = {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_decks_library_page.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            search_query=None,
            is_favourite=False,
            cursor=None,
            limit=50,
        )

    async def test_passes_normalized_filters_and_pagination(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_decks_library_page.return_value = {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        response = await client.get(
            "/bff/library/decks",
            params={
                "q": "  FaVoUrItEs  ",
                "is_favourite": True,
                "cursor": "deck-cursor",
                "limit": 100,
            },
        )

        expected = {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_decks_library_page.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            search_query="favourites",
            is_favourite=True,
            cursor="deck-cursor",
            limit=100,
        )

    @pytest.mark.parametrize(
        ("params", "expected_detail"),
        [
            pytest.param(
                {"q": ""},
                {
                    "type": "string_too_short",
                    "loc": ["query", "q"],
                    "msg": "String should have at least 1 character",
                    "input": "",
                    "ctx": {"min_length": 1},
                },
                id="query_empty",
            ),
            pytest.param(
                {"q": "a" * 51},
                {
                    "type": "string_too_long",
                    "loc": ["query", "q"],
                    "msg": "String should have at most 50 characters",
                    "input": "a" * 51,
                    "ctx": {"max_length": 50},
                },
                id="query_too_long",
            ),
            pytest.param(
                {"is_favourite": "not-a-bool"},
                {
                    "type": "bool_parsing",
                    "loc": ["query", "is_favourite"],
                    "msg": (
                        "Input should be a valid boolean, unable to interpret input"
                    ),
                    "input": "not-a-bool",
                },
                id="invalid_favourite_filter",
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
                {"limit": 101},
                {
                    "type": "less_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be less than or equal to 100",
                    "input": "101",
                    "ctx": {"le": 100},
                },
                id="limit_above_maximum",
            ),
        ],
    )
    async def test_rejects_invalid_query_params(
        self,
        client: AsyncClient,
        params,
        expected_detail,
        bff_service: AsyncMock,
    ):
        response = await client.get("/bff/library/decks", params=params)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
        }
        bff_service.get_decks_library_page.assert_not_awaited()

    async def test_returns_404_when_user_deck_progress_missing(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_decks_library_page.side_effect = UserDeckNotFoundError()

        response = await client.get("/bff/library/decks")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"message": "User deck progress not found"}
        bff_service.get_decks_library_page.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            search_query=None,
            is_favourite=False,
            cursor=None,
            limit=50,
        )


class TestGetCardsLibraryPage:
    async def test_returns_cards_library_page(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_cards_library_page.return_value = {
            "items": [
                {
                    "card": {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "front_text": "привет",
                        "back_text": "hello",
                        "front_lang": "ru",
                        "back_lang": "en",
                        "updated_at": "2026-08-15T15:00:00Z",
                    }
                }
            ],
            "next_cursor": "next-card-cursor",
            "has_more": True,
        }

        response = await client.get("/bff/library/cards")

        expected = {
            "items": [
                {
                    "card": {
                        "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "front_text": "привет",
                        "back_text": "hello",
                        "front_lang": "ru",
                        "back_lang": "en",
                        "updated_at": "2026-08-15T15:00:00Z",
                    }
                }
            ],
            "next_cursor": "next-card-cursor",
            "has_more": True,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_cards_library_page.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            search_query=None,
            cursor=None,
            limit=50,
        )

    async def test_returns_empty_cards_library_page(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_cards_library_page.return_value = {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        response = await client.get("/bff/library/cards")

        expected = {"items": [], "next_cursor": None, "has_more": False}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_cards_library_page.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            search_query=None,
            cursor=None,
            limit=50,
        )

    async def test_passes_normalized_search_and_pagination(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.get_cards_library_page.return_value = {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        response = await client.get(
            "/bff/library/cards",
            params={
                "q": "  HeLLo  ",
                "cursor": "card-cursor",
                "limit": 25,
            },
        )

        expected = {"items": [], "next_cursor": None, "has_more": False}

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.get_cards_library_page.assert_awaited_once_with(
            user_id=current_user.id,
            user_uuid=current_user.uuid,
            search_query="hello",
            cursor="card-cursor",
            limit=25,
        )

    @pytest.mark.parametrize(
        ("params", "expected_detail"),
        [
            pytest.param(
                {"q": ""},
                {
                    "type": "string_too_short",
                    "loc": ["query", "q"],
                    "msg": "String should have at least 1 character",
                    "input": "",
                    "ctx": {"min_length": 1},
                },
                id="query_empty",
            ),
            pytest.param(
                {"q": "a" * 51},
                {
                    "type": "string_too_long",
                    "loc": ["query", "q"],
                    "msg": "String should have at most 50 characters",
                    "input": "a" * 51,
                    "ctx": {"max_length": 50},
                },
                id="query_too_long",
            ),
            pytest.param(
                {"limit": "not-an-int"},
                {
                    "type": "int_parsing",
                    "loc": ["query", "limit"],
                    "msg": (
                        "Input should be a valid integer, unable to parse string as an integer"
                    ),
                    "input": "not-an-int",
                },
                id="limit_not_integer",
            ),
        ],
    )
    async def test_rejects_invalid_query_params(
        self,
        client: AsyncClient,
        params,
        expected_detail,
        bff_service: AsyncMock,
    ):
        response = await client.get("/bff/library/cards", params=params)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
        }
        bff_service.get_cards_library_page.assert_not_awaited()


class TestStartPracticeSession:
    async def test_starts_practice_session(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        payload = {"prompt_side": "front", "words_per_session": 10}
        bff_service.start_practice_session.return_value = {
            "training_session_uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "deck_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "prompt_side": "front",
            "answer_side": "back",
            "total_count": 10,
            "answered_count": 0,
            "correct_count": 0,
            "wrong_count": 0,
            "started_at": "2026-08-15T16:00:00Z",
            "cards": [
                {
                    "sequence_number": 1,
                    "prompt_text": "привет",
                    "prompt_language": "ru",
                    "answer_language": "en",
                }
            ],
        }

        response = await client.post(
            "/bff/practice/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/start",
            json=payload,
        )

        expected = {
            "training_session_uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "deck_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "prompt_side": "front",
            "answer_side": "back",
            "total_count": 10,
            "answered_count": 0,
            "correct_count": 0,
            "wrong_count": 0,
            "started_at": "2026-08-15T16:00:00Z",
            "cards": [
                {
                    "sequence_number": 1,
                    "prompt_text": "привет",
                    "prompt_language": "ru",
                    "answer_language": "en",
                }
            ],
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.start_practice_session.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            prompt_side="front",
            words_per_session=10,
        )

    async def test_accepts_minimum_words_and_back_prompt(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        payload = {"prompt_side": "back", "words_per_session": 1}
        bff_service.start_practice_session.return_value = {
            "training_session_uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "deck_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "prompt_side": "back",
            "answer_side": "front",
            "total_count": 1,
            "answered_count": 0,
            "correct_count": 0,
            "wrong_count": 0,
            "started_at": "2026-08-15T16:00:00Z",
            "cards": [],
        }

        response = await client.post(
            "/bff/practice/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/start",
            json=payload,
        )

        expected = {
            "training_session_uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "deck_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "prompt_side": "back",
            "answer_side": "front",
            "total_count": 1,
            "answered_count": 0,
            "correct_count": 0,
            "wrong_count": 0,
            "started_at": "2026-08-15T16:00:00Z",
            "cards": [],
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.start_practice_session.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            prompt_side="back",
            words_per_session=1,
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {"prompt_side": "middle", "words_per_session": 10},
                {
                    "type": "literal_error",
                    "loc": ["body", "prompt_side"],
                    "msg": "Input should be 'front' or 'back'",
                    "input": "middle",
                    "ctx": {"expected": "'front' or 'back'"},
                },
                id="invalid_prompt_side",
            ),
            pytest.param(
                {"prompt_side": "front", "words_per_session": 0},
                {
                    "type": "greater_than_equal",
                    "loc": ["body", "words_per_session"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": 0,
                    "ctx": {"ge": 1},
                },
                id="words_below_minimum",
            ),
        ],
    )
    async def test_rejects_invalid_payload(
        self,
        client: AsyncClient,
        payload,
        expected_detail,
        bff_service: AsyncMock,
    ):
        response = await client.post(
            "/bff/practice/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/start",
            json=payload,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
        }
        bff_service.start_practice_session.assert_not_awaited()

    @pytest.mark.parametrize(
        ("payload", "field"),
        [
            pytest.param(
                {"words_per_session": 10},
                "prompt_side",
                id="prompt_side_missing",
            ),
            pytest.param(
                {"prompt_side": "front"},
                "words_per_session",
                id="words_per_session_missing",
            ),
        ],
    )
    async def test_rejects_missing_payload_field(
        self,
        client: AsyncClient,
        payload,
        field,
        bff_service: AsyncMock,
    ):
        response = await client.post(
            "/bff/practice/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/start",
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
        bff_service.start_practice_session.assert_not_awaited()

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
                DeckIsEmptyError(),
                status.HTTP_409_CONFLICT,
                "Deck is empty",
                id="deck_empty",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        service_error,
        expected_status,
        expected_message,
        bff_service: AsyncMock,
    ):
        bff_service.start_practice_session.side_effect = service_error

        response = await client.post(
            "/bff/practice/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/start",
            json={"prompt_side": "front", "words_per_session": 10},
        )

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}
        bff_service.start_practice_session.assert_awaited_once_with(
            user_id=current_user.id,
            deck_uuid=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            prompt_side="front",
            words_per_session=10,
        )

    async def test_rejects_invalid_deck_uuid(
        self,
        client: AsyncClient,
        bff_service: AsyncMock,
    ):
        response = await client.post(
            "/bff/practice/not-a-uuid/start",
            json={"prompt_side": "front", "words_per_session": 10},
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
        bff_service.start_practice_session.assert_not_awaited()


class TestResumePracticeSession:
    async def test_resumes_practice_session(
        self,
        client: AsyncClient,
        current_user,
        bff_service: AsyncMock,
    ):
        bff_service.resume_practice_session.return_value = {
            "training_session_uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "deck_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "prompt_side": "front",
            "answer_side": "back",
            "total_count": 10,
            "answered_count": 3,
            "correct_count": 2,
            "wrong_count": 1,
            "started_at": "2026-08-15T16:00:00Z",
            "cards": [
                {
                    "sequence_number": 4,
                    "prompt_text": "пока",
                    "prompt_language": "ru",
                    "answer_language": "en",
                }
            ],
        }

        response = await client.get(
            "/bff/practice/dddddddd-dddd-dddd-dddd-dddddddddddd/resume"
        )

        expected = {
            "training_session_uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "deck_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "prompt_side": "front",
            "answer_side": "back",
            "total_count": 10,
            "answered_count": 3,
            "correct_count": 2,
            "wrong_count": 1,
            "started_at": "2026-08-15T16:00:00Z",
            "cards": [
                {
                    "sequence_number": 4,
                    "prompt_text": "пока",
                    "prompt_language": "ru",
                    "answer_language": "en",
                }
            ],
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        bff_service.resume_practice_session.assert_awaited_once_with(
            user_id=current_user.id,
            training_session_uuid=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                TrainingSessionNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Training session not found",
                id="session_not_found",
            ),
            pytest.param(
                DeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Deck not found",
                id="deck_not_found",
            ),
            pytest.param(
                TrainingSessionAlreadyFinishedError(),
                status.HTTP_409_CONFLICT,
                "Training session already finished",
                id="session_already_finished",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        service_error,
        expected_status,
        expected_message,
        bff_service: AsyncMock,
    ):
        bff_service.resume_practice_session.side_effect = service_error

        response = await client.get(
            "/bff/practice/dddddddd-dddd-dddd-dddd-dddddddddddd/resume"
        )

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}
        bff_service.resume_practice_session.assert_awaited_once_with(
            user_id=current_user.id,
            training_session_uuid=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        )

    async def test_rejects_invalid_training_session_uuid(
        self,
        client: AsyncClient,
        bff_service: AsyncMock,
    ):
        response = await client.get("/bff/practice/not-a-uuid/resume")

        expected = {
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "training_session_uuid"],
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
        bff_service.resume_practice_session.assert_not_awaited()
