from datetime import UTC, date, datetime, timedelta, timezone
from http.cookies import SimpleCookie
import re
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from app.auth.deps import get_current_user, get_current_user_with_settings
from app.auth.errors import AccessTokenNotFoundError, CaptchaError, InvalidTokenError
from app.common.schemas import CursorPage
from app.decks.schemas import (
    DeckListItemResponse,
    DeckResponse,
    DeckViewerStateResponse,
)
from app.errors import RequestValueError
from app.training_sessions.models import TrainingSessionStatus
from app.users.errors import (
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    PermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.users.schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    UpdateUserSettingsRequest,
)
from tests.unit.factories import (
    make_deck,
    make_training_session,
    make_user,
    make_user_deck,
    make_user_settings,
)


class TestGetMe:
    async def test_returns_current_user(
        self,
        client: AsyncClient,
        current_user_with_settings,
    ):
        response = await client.get("/users/me")

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "test-user",
            "email": "test@example.com",
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

    @pytest.mark.parametrize(
        "current_user",
        [
            {
                "id": 99,
                "username": "another-user",
                "email": "another@example.com",
            }
        ],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "user_settings",
        [
            {
                "locale": "ru-RU",
                "theme": "dark",
                "show_previews_for_long": False,
            }
        ],
        indirect=True,
    )
    async def test_returns_user_with_custom_settings(
        self,
        client: AsyncClient,
        current_user_with_settings,
    ):
        response = await client.get("/users/me")

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "another-user",
            "email": "another@example.com",
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "ru-RU",
                "theme": "dark",
                "show_previews_for_long": False,
            },
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected


class TestGetUserDailyActivity:
    async def test_returns_daily_activity_from_datetime(
        self,
        client: AsyncClient,
        current_user,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_user_activity.return_value = {
            date(2026, 8, 1): 2,
            date(2026, 8, 3): 5,
        }

        response = await client.get(
            "/users/me/daily-activity",
            params={"from_datetime": "2026-08-01T00:00:00Z"},
        )

        expected = {
            "2026-08-01": 2,
            "2026-08-03": 5,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.get_user_activity.assert_awaited_once_with(
            user_id=current_user.id,
            from_datetime=datetime(2026, 8, 1, tzinfo=UTC),
            to_datetime=None,
        )

    async def test_passes_datetime_range_and_returns_empty_activity(
        self,
        client: AsyncClient,
        current_user,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_user_activity.return_value = {}

        response = await client.get(
            "/users/me/daily-activity",
            params={
                "from_datetime": "2026-08-01T10:30:00+03:00",
                "to_datetime": "2026-08-31T23:59:59+03:00",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {}

        training_session_service.get_user_activity.assert_awaited_once_with(
            user_id=current_user.id,
            from_datetime=datetime(
                2026,
                8,
                1,
                10,
                30,
                tzinfo=timezone(timedelta(hours=3)),
            ),
            to_datetime=datetime(
                2026,
                8,
                31,
                23,
                59,
                59,
                tzinfo=timezone(timedelta(hours=3)),
            ),
        )

    async def test_rejects_missing_from_datetime(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        response = await client.get("/users/me/daily-activity")

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "missing",
                    "loc": ["query", "from_datetime"],
                    "msg": "Field required",
                    "input": None,
                }
            ],
        }

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == expected

        training_session_service.get_user_activity.assert_not_awaited()

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            pytest.param(
                {"from_datetime": "not-a-date"},
                "from_datetime",
                id="from_datetime_invalid",
            ),
            pytest.param(
                {
                    "from_datetime": "2026-08-01T00:00:00Z",
                    "to_datetime": "not-a-date",
                },
                "to_datetime",
                id="to_datetime_invalid",
            ),
        ],
    )
    async def test_rejects_invalid_datetime(
        self,
        client: AsyncClient,
        params,
        field,
        training_session_service: AsyncMock,
    ):
        response = await client.get(
            "/users/me/daily-activity",
            params=params,
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "datetime_from_date_parsing",
                    "loc": ["query", field],
                    "msg": (
                        "Input should be a valid datetime or date, "
                        "invalid character in year"
                    ),
                    "input": "not-a-date",
                    "ctx": {"error": "invalid character in year"},
                }
            ],
        }

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == expected

        training_session_service.get_user_activity.assert_not_awaited()


class TestChangeSettings:
    async def test_updates_user_settings(
        self,
        client: AsyncClient,
        current_user,
        user_service: AsyncMock,
    ):
        payload = {
            "locale": "ru-RU",
            "theme": "dark",
            "show_previews_for_long": False,
        }
        updated_user_settings = make_user_settings(**payload)

        user_service.update_user_settings.return_value = updated_user_settings

        response = await client.patch(
            "/users/me/settings",
            json=payload,
        )

        expected = {
            "locale": "ru-RU",
            "theme": "dark",
            "show_previews_for_long": False,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        user_service.update_user_settings.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UpdateUserSettingsRequest(**payload),
        )

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            pytest.param(
                {"locale": "ru-RU"},
                {
                    "locale": "ru-RU",
                    "theme": "system",
                    "show_previews_for_long": True,
                },
                id="locale_ru",
            ),
            pytest.param(
                {"locale": "en-US"},
                {
                    "locale": "en-US",
                    "theme": "system",
                    "show_previews_for_long": True,
                },
                id="locale_en",
            ),
            pytest.param(
                {"theme": "dark"},
                {
                    "locale": "ru-RU",
                    "theme": "dark",
                    "show_previews_for_long": True,
                },
                id="theme_dark",
            ),
            pytest.param(
                {"theme": "light"},
                {
                    "locale": "ru-RU",
                    "theme": "light",
                    "show_previews_for_long": True,
                },
                id="theme_light",
            ),
            pytest.param(
                {"theme": "system"},
                {
                    "locale": "ru-RU",
                    "theme": "system",
                    "show_previews_for_long": True,
                },
                id="theme_system",
            ),
            pytest.param(
                {"show_previews_for_long": True},
                {
                    "locale": "ru-RU",
                    "theme": "system",
                    "show_previews_for_long": True,
                },
                id="previews_enabled",
            ),
            pytest.param(
                {"show_previews_for_long": False},
                {
                    "locale": "ru-RU",
                    "theme": "system",
                    "show_previews_for_long": False,
                },
                id="previews_disabled",
            ),
        ],
    )
    async def test_updates_single_setting(
        self,
        client: AsyncClient,
        current_user,
        payload,
        expected,
        user_service: AsyncMock,
    ):
        updated_settings = make_user_settings(**payload)

        user_service.update_user_settings.return_value = updated_settings

        response = await client.patch(
            "/users/me/settings",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        user_service.update_user_settings.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UpdateUserSettingsRequest(**payload),
        )

    async def test_returns_422_for_empty_payload(
        self,
        client: AsyncClient,
        current_user,
        user_service: AsyncMock,
    ):
        payload = {}
        user_service.update_user_settings.side_effect = RequestValueError(
            message="Update body is empty",
            failed_field="body",
        )

        response = await client.patch(
            "/users/me/settings",
            json=payload,
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "value_error",
                    "loc": ["body", "body"],
                    "msg": "Update body is empty",
                    "input": None,
                }
            ],
        }

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == expected

        user_service.update_user_settings.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UpdateUserSettingsRequest(**payload),
        )


class TestGetMyDecks:
    async def test_returns_current_user_decks(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_owned_decks.return_value = CursorPage(
            items=[deck],
            next_cursor=None,
            has_more=False,
        )

        response = await client.get("/users/me/decks")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "owner_uuid": ("0198ad01-b200-7000-8000-000000000042"),
                    "owner_username": "test-user",
                    "title": "Test deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                }
            ],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.json() == expected

        deck_service.get_owned_decks.assert_awaited_once_with(
            owner_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=30,
        )

    async def test_returns_multiple_decks(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        decks = [
            make_deck(
                title="First deck",
            ),
            make_deck(
                title="Second deck",
            ),
        ]

        deck_service.get_owned_decks.return_value = CursorPage(
            items=decks,
            next_cursor=None,
            has_more=False,
        )

        response = await client.get("/users/me/decks")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "owner_uuid": ("0198ad01-b200-7000-8000-000000000042"),
                    "owner_username": "test-user",
                    "title": "First deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                },
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "owner_uuid": ("0198ad01-b200-7000-8000-000000000042"),
                    "owner_username": "test-user",
                    "title": "Second deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                },
            ],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.json() == expected

        deck_service.get_owned_decks.assert_awaited_once_with(
            owner_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=30,
        )

    async def test_returns_empty_page(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        deck_service.get_owned_decks.return_value = CursorPage(
            items=[],
            next_cursor=None,
            has_more=False,
        )

        response = await client.get("/users/me/decks")

        assert response.status_code == status.HTTP_200_OK

        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_owned_decks.assert_awaited_once_with(
            owner_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=30,
        )

    async def test_returns_next_cursor(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        next_cursor = "next-page-cursor"

        deck_service.get_owned_decks.return_value = CursorPage(
            items=[deck],
            next_cursor=next_cursor,
            has_more=True,
        )

        response = await client.get("/users/me/decks")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "owner_uuid": ("0198ad01-b200-7000-8000-000000000042"),
                    "owner_username": "test-user",
                    "title": "Test deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                }
            ],
            "next_cursor": next_cursor,
            "has_more": True,
        }

        assert response.json() == expected

        deck_service.get_owned_decks.assert_awaited_once_with(
            owner_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=30,
        )

    @pytest.mark.parametrize(
        ("limit", "cursor"),
        [
            pytest.param(50, "some-cursor", id="ordinary_values"),
            pytest.param(1, "some-cursor", id="minimum_limit"),
            pytest.param(100, "some-cursor", id="maximum_limit"),
            pytest.param(30, "a" * 512, id="maximum_cursor_length"),
        ],
    )
    async def test_passes_pagination_params(
        self,
        client: AsyncClient,
        current_user,
        limit,
        cursor,
        deck_service: AsyncMock,
    ):
        deck_service.get_owned_decks.return_value = CursorPage(
            items=[],
            next_cursor=None,
            has_more=False,
        )

        response = await client.get(
            "/users/me/decks",
            params={
                "limit": limit,
                "cursor": cursor,
            },
        )

        assert response.status_code == status.HTTP_200_OK

        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_owned_decks.assert_awaited_once_with(
            owner_id=current_user.id,
            search_query=None,
            cursor=cursor,
            limit=limit,
        )

    @pytest.mark.parametrize(
        ("raw_query", "normalized_query"),
        [
            pytest.param(
                "english",
                "english",
                id="unchanged",
            ),
            pytest.param(
                "  EnGliSh Words  ",
                "english words",
                id="strips_whitespace_and_lowercases",
            ),
            pytest.param(
                "a",
                "a",
                id="minimum_length",
            ),
            pytest.param(
                "a" * 50,
                "a" * 50,
                id="maximum_length",
            ),
        ],
    )
    async def test_passes_normalized_search_query(
        self,
        client: AsyncClient,
        current_user,
        raw_query,
        normalized_query,
        deck_service: AsyncMock,
    ):
        deck_service.get_owned_decks.return_value = CursorPage(
            items=[],
            next_cursor=None,
            has_more=False,
        )

        response = await client.get(
            "/users/me/decks",
            params={"q": raw_query},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_owned_decks.assert_awaited_once_with(
            owner_id=current_user.id,
            search_query=normalized_query,
            cursor=None,
            limit=30,
        )

    @pytest.mark.parametrize(
        ("limit", "expected_detail"),
        [
            pytest.param(
                0,
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="below_minimum",
            ),
            pytest.param(
                101,
                {
                    "type": "less_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be less than or equal to 100",
                    "input": "101",
                    "ctx": {"le": 100},
                },
                id="above_maximum",
            ),
        ],
    )
    async def test_rejects_invalid_limit(
        self,
        client: AsyncClient,
        limit,
        expected_detail,
        deck_service: AsyncMock,
    ):
        response = await client.get(
            "/users/me/decks",
            params={
                "limit": limit,
            },
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_owned_decks.assert_not_awaited()

    @pytest.mark.parametrize(
        ("search_query", "expected_detail"),
        [
            pytest.param(
                " ",
                {
                    "type": "string_too_short",
                    "loc": ["query", "q"],
                    "msg": "String should have at least 1 character",
                    "input": " ",
                    "ctx": {"min_length": 1},
                },
                id="empty_after_normalization",
            ),
            pytest.param(
                "a" * 51,
                {
                    "type": "string_too_long",
                    "loc": ["query", "q"],
                    "msg": "String should have at most 50 characters",
                    "input": "a" * 51,
                    "ctx": {"max_length": 50},
                },
                id="above_maximum_length",
            ),
        ],
    )
    async def test_rejects_invalid_search_query(
        self,
        client: AsyncClient,
        search_query,
        expected_detail,
        deck_service: AsyncMock,
    ):
        response = await client.get(
            "/users/me/decks",
            params={
                "q": search_query,
            },
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_owned_decks.assert_not_awaited()

    async def test_rejects_too_long_cursor(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        cursor = "a" * 513

        response = await client.get(
            "/users/me/decks",
            params={"cursor": cursor},
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "string_too_long",
                    "loc": ["query", "cursor"],
                    "msg": "String should have at most 512 characters",
                    "input": cursor,
                    "ctx": {"max_length": 512},
                }
            ],
        }

        deck_service.get_owned_decks.assert_not_awaited()


class TestGetMyTrainingSessions:
    async def test_returns_current_user_training_sessions(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_sessions_by_user_uuid.return_value = (
            [training_session],
            None,
            False,
        )

        response = await client.get("/users/me/training-sessions")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000400",
                    "deck_uuid": ("0198ad01-b200-7000-8000-000000000200"),
                    "deck_title": "Test deck",
                    "status": "in_progress",
                    "requested_count": 10,
                    "answered_count": 3,
                    "correct_count": 2,
                    "wrong_count": 1,
                    "prompt_side": "front",
                    "answer_side": "back",
                    "started_at": "2026-08-15T16:00:00Z",
                    "finished_at": None,
                }
            ],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.json() == expected

        (
            training_session_service.get_sessions_by_user_uuid.assert_awaited_once_with(
                user_uuid=current_user.uuid,
                status=None,
                cursor=None,
                limit=20,
            )
        )

    async def test_returns_multiple_training_sessions(
        self,
        client: AsyncClient,
        current_user,
        training_session_service: AsyncMock,
    ):
        training_sessions = [
            make_training_session(
                status=TrainingSessionStatus.IN_PROGRESS,
            ),
            make_training_session(
                status=TrainingSessionStatus.COMPLETED,
                requested_count=3,
                finished_at=datetime(2026, 8, 15, 17, 0, tzinfo=UTC),
            ),
        ]

        training_session_service.get_sessions_by_user_uuid.return_value = (
            training_sessions,
            None,
            False,
        )

        response = await client.get("/users/me/training-sessions")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000400",
                    "deck_uuid": ("0198ad01-b200-7000-8000-000000000200"),
                    "deck_title": "Test deck",
                    "status": "in_progress",
                    "requested_count": 10,
                    "answered_count": 3,
                    "correct_count": 2,
                    "wrong_count": 1,
                    "prompt_side": "front",
                    "answer_side": "back",
                    "started_at": "2026-08-15T16:00:00Z",
                    "finished_at": None,
                },
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000400",
                    "deck_uuid": ("0198ad01-b200-7000-8000-000000000200"),
                    "deck_title": "Test deck",
                    "status": "completed",
                    "requested_count": 3,
                    "answered_count": 3,
                    "correct_count": 2,
                    "wrong_count": 1,
                    "prompt_side": "front",
                    "answer_side": "back",
                    "started_at": "2026-08-15T16:00:00Z",
                    "finished_at": "2026-08-15T17:00:00Z",
                },
            ],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.json() == expected

        (
            training_session_service.get_sessions_by_user_uuid.assert_awaited_once_with(
                user_uuid=current_user.uuid,
                status=None,
                cursor=None,
                limit=20,
            )
        )

    async def test_returns_empty_page(
        self,
        client: AsyncClient,
        current_user,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_sessions_by_user_uuid.return_value = (
            [],
            None,
            False,
        )

        response = await client.get("/users/me/training-sessions")

        assert response.status_code == status.HTTP_200_OK

        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        (
            training_session_service.get_sessions_by_user_uuid.assert_awaited_once_with(
                user_uuid=current_user.uuid,
                status=None,
                cursor=None,
                limit=20,
            )
        )

    async def test_returns_next_cursor(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        next_cursor = "next-page-cursor"

        training_session_service.get_sessions_by_user_uuid.return_value = (
            [training_session],
            next_cursor,
            True,
        )

        response = await client.get("/users/me/training-sessions")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000400",
                    "deck_uuid": ("0198ad01-b200-7000-8000-000000000200"),
                    "deck_title": "Test deck",
                    "status": "in_progress",
                    "requested_count": 10,
                    "answered_count": 3,
                    "correct_count": 2,
                    "wrong_count": 1,
                    "prompt_side": "front",
                    "answer_side": "back",
                    "started_at": "2026-08-15T16:00:00Z",
                    "finished_at": None,
                }
            ],
            "next_cursor": next_cursor,
            "has_more": True,
        }

        assert response.json() == expected

        (
            training_session_service.get_sessions_by_user_uuid.assert_awaited_once_with(
                user_uuid=current_user.uuid,
                status=None,
                cursor=None,
                limit=20,
            )
        )

    @pytest.mark.parametrize(
        "session_status",
        [
            pytest.param(
                TrainingSessionStatus.IN_PROGRESS,
                id="in_progress",
            ),
            pytest.param(
                TrainingSessionStatus.COMPLETED,
                id="completed",
            ),
            pytest.param(
                TrainingSessionStatus.ABANDONED,
                id="abandoned",
            ),
        ],
    )
    async def test_filters_by_status(
        self,
        client: AsyncClient,
        current_user,
        session_status,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_sessions_by_user_uuid.return_value = (
            [],
            None,
            False,
        )

        response = await client.get(
            "/users/me/training-sessions",
            params={
                "status": session_status.value,
            },
        )

        assert response.status_code == status.HTTP_200_OK

        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        (
            training_session_service.get_sessions_by_user_uuid.assert_awaited_once_with(
                user_uuid=current_user.uuid,
                status=session_status,
                cursor=None,
                limit=20,
            )
        )

    @pytest.mark.parametrize(
        ("limit", "cursor"),
        [
            pytest.param(50, "some-cursor", id="ordinary_values"),
            pytest.param(1, "some-cursor", id="minimum_limit"),
            pytest.param(100, "some-cursor", id="maximum_limit"),
            pytest.param(20, "a" * 512, id="maximum_cursor_length"),
        ],
    )
    async def test_passes_pagination_params(
        self,
        client: AsyncClient,
        current_user,
        limit,
        cursor,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_sessions_by_user_uuid.return_value = (
            [],
            None,
            False,
        )

        response = await client.get(
            "/users/me/training-sessions",
            params={
                "limit": limit,
                "cursor": cursor,
            },
        )

        assert response.status_code == status.HTTP_200_OK

        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        (
            training_session_service.get_sessions_by_user_uuid.assert_awaited_once_with(
                user_uuid=current_user.uuid,
                status=None,
                cursor=cursor,
                limit=limit,
            )
        )

    async def test_passes_all_filters(
        self,
        client: AsyncClient,
        current_user,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_sessions_by_user_uuid.return_value = (
            [],
            None,
            False,
        )

        response = await client.get(
            "/users/me/training-sessions",
            params={
                "status": "completed",
                "limit": 40,
                "cursor": "some-cursor",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        (
            training_session_service.get_sessions_by_user_uuid.assert_awaited_once_with(
                user_uuid=current_user.uuid,
                status=TrainingSessionStatus.COMPLETED,
                cursor="some-cursor",
                limit=40,
            )
        )

    @pytest.mark.parametrize(
        ("limit", "expected_detail"),
        [
            pytest.param(
                0,
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="below_minimum",
            ),
            pytest.param(
                101,
                {
                    "type": "less_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be less than or equal to 100",
                    "input": "101",
                    "ctx": {"le": 100},
                },
                id="above_maximum",
            ),
        ],
    )
    async def test_rejects_invalid_limit(
        self,
        client: AsyncClient,
        limit,
        expected_detail,
        training_session_service: AsyncMock,
    ):
        response = await client.get(
            "/users/me/training-sessions",
            params={
                "limit": limit,
            },
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        (training_session_service.get_sessions_by_user_uuid.assert_not_awaited())

    async def test_rejects_invalid_status(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        response = await client.get(
            "/users/me/training-sessions",
            params={
                "status": "invalid",
            },
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "enum",
                    "loc": ["query", "status"],
                    "msg": (
                        "Input should be 'in_progress', 'completed' or 'abandoned'"
                    ),
                    "input": "invalid",
                    "ctx": {"expected": ("'in_progress', 'completed' or 'abandoned'")},
                }
            ],
        }

        (training_session_service.get_sessions_by_user_uuid.assert_not_awaited())

    async def test_rejects_too_long_cursor(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        cursor = "a" * 513

        response = await client.get(
            "/users/me/training-sessions",
            params={"cursor": cursor},
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "string_too_long",
                    "loc": ["query", "cursor"],
                    "msg": "String should have at most 512 characters",
                    "input": cursor,
                    "ctx": {"max_length": 512},
                }
            ],
        }

        (training_session_service.get_sessions_by_user_uuid.assert_not_awaited())


class TestGetMySavedDecks:
    async def test_returns_saved_decks(
        self,
        client: AsyncClient,
        current_user,
        deck,
        user_deck_service: AsyncMock,
    ):
        user_deck = make_user_deck(is_saved=True)
        saved_deck = DeckListItemResponse(
            deck=DeckResponse.model_validate(deck),
            viewer_state=DeckViewerStateResponse.validate(user_deck),
        )

        user_deck_service.get_page_of_saved_decks_by_user_id.return_value = [saved_deck]

        response = await client.get("/users/me/decks/saved")

        assert response.status_code == status.HTTP_200_OK

        expected = [
            {
                "deck": {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "owner_uuid": ("0198ad01-b200-7000-8000-000000000042"),
                    "owner_username": "test-user",
                    "title": "Test deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                },
                "viewer_state": {
                    "sessions_count": 0,
                    "correct_count": 0,
                    "wrong_count": 0,
                    "accuracy": 0,
                    "last_studied_at": None,
                    "is_favourite": False,
                    "is_saved": True,
                },
            }
        ]

        assert response.json() == expected

        (
            user_deck_service.get_page_of_saved_decks_by_user_id.assert_awaited_once_with(
                user_id=current_user.id,
                page=1,
                page_size=20,
            )
        )

    async def test_returns_multiple_saved_decks(
        self,
        client: AsyncClient,
        current_user,
        user_deck_service: AsyncMock,
    ):
        first_deck = make_deck(
            title="first deck",
        )
        second_deck = make_deck(
            title="second deck",
        )

        first_user_deck = make_user_deck(
            deck_id=first_deck.id,
            sessions_count=10,
            correct_count=8,
            wrong_count=2,
            is_saved=True,
        )
        second_user_deck = make_user_deck(
            deck_id=second_deck.id,
            sessions_count=5,
            correct_count=3,
            wrong_count=2,
            is_saved=True,
        )

        saved_decks = [
            DeckListItemResponse(
                deck=DeckResponse.model_validate(first_deck),
                viewer_state=DeckViewerStateResponse.validate(first_user_deck),
            ),
            DeckListItemResponse(
                deck=DeckResponse.model_validate(second_deck),
                viewer_state=DeckViewerStateResponse.validate(second_user_deck),
            ),
        ]

        (
            user_deck_service.get_page_of_saved_decks_by_user_id.return_value
        ) = saved_decks

        response = await client.get("/users/me/decks/saved")

        assert response.status_code == status.HTTP_200_OK

        expected = [
            {
                "deck": {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "owner_uuid": ("0198ad01-b200-7000-8000-000000000042"),
                    "owner_username": "test-user",
                    "title": "first deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                },
                "viewer_state": {
                    "sessions_count": 10,
                    "correct_count": 8,
                    "wrong_count": 2,
                    "accuracy": 80,
                    "last_studied_at": None,
                    "is_favourite": False,
                    "is_saved": True,
                },
            },
            {
                "deck": {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "owner_uuid": ("0198ad01-b200-7000-8000-000000000042"),
                    "owner_username": "test-user",
                    "title": "second deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                },
                "viewer_state": {
                    "sessions_count": 5,
                    "correct_count": 3,
                    "wrong_count": 2,
                    "accuracy": 60,
                    "last_studied_at": None,
                    "is_favourite": False,
                    "is_saved": True,
                },
            },
        ]

        assert response.json() == expected

        (
            user_deck_service.get_page_of_saved_decks_by_user_id.assert_awaited_once_with(
                user_id=current_user.id,
                page=1,
                page_size=20,
            )
        )

    async def test_returns_empty_list(
        self,
        client: AsyncClient,
        current_user,
        user_deck_service: AsyncMock,
    ):
        (user_deck_service.get_page_of_saved_decks_by_user_id.return_value) = []

        response = await client.get("/users/me/decks/saved")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        (
            user_deck_service.get_page_of_saved_decks_by_user_id.assert_awaited_once_with(
                user_id=current_user.id,
                page=1,
                page_size=20,
            )
        )

    @pytest.mark.parametrize(
        ("page", "page_size"),
        [
            pytest.param(3, 50, id="ordinary_values"),
            pytest.param(1, 1, id="minimum_values"),
            pytest.param(3, 100, id="maximum_page_size"),
        ],
    )
    async def test_passes_pagination_params(
        self,
        client: AsyncClient,
        current_user,
        page,
        page_size,
        user_deck_service: AsyncMock,
    ):
        (user_deck_service.get_page_of_saved_decks_by_user_id.return_value) = []

        response = await client.get(
            "/users/me/decks/saved",
            params={
                "page": page,
                "page_size": page_size,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        (
            user_deck_service.get_page_of_saved_decks_by_user_id.assert_awaited_once_with(
                user_id=current_user.id,
                page=page,
                page_size=page_size,
            )
        )

    @pytest.mark.parametrize(
        ("params", "expected_detail"),
        [
            pytest.param(
                {"page": 0},
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "page"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="page_zero",
            ),
            pytest.param(
                {"page": -1},
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "page"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "-1",
                    "ctx": {"ge": 1},
                },
                id="page_negative",
            ),
            pytest.param(
                {"page_size": 0},
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "page_size"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="page_size_below_minimum",
            ),
            pytest.param(
                {"page_size": 101},
                {
                    "type": "less_than_equal",
                    "loc": ["query", "page_size"],
                    "msg": "Input should be less than or equal to 100",
                    "input": "101",
                    "ctx": {"le": 100},
                },
                id="page_size_above_maximum",
            ),
        ],
    )
    async def test_rejects_invalid_pagination(
        self,
        client: AsyncClient,
        params,
        expected_detail,
        user_deck_service: AsyncMock,
    ):
        response = await client.get(
            "/users/me/decks/saved",
            params=params,
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        (user_deck_service.get_page_of_saved_decks_by_user_id.assert_not_awaited())


class TestGetUserProfile:
    @pytest.mark.parametrize("optional_current_user", [None, make_user()], indirect=True)
    async def test_returns_profile_for_anonymous_or_authenticated_viewer(
        self, client, optional_current_user, user_service,
    ):
        user_service.get_user_profile.return_value = make_user(
            deck_count=3, total_saves_count=7,
        )

        response = await client.get("/users/profile/test-user")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "test-user",
            "created_at": "2026-08-15T12:00:00Z",
            "deck_count": 3,
            "total_saves_count": 7,
        }
        user_service.get_user_profile.assert_awaited_once_with(
            viewer_id=optional_current_user.id if optional_current_user else None,
            username="test-user",
        )

    async def test_preserves_username_case_and_strips_spaces(
        self, client, current_user, user_service,
    ):
        user_service.get_user_profile.return_value = make_user(
            username="Test-User", deck_count=0, total_saves_count=0,
        )

        response = await client.get("/users/profile/%20Test-User%20")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "Test-User",
            "created_at": "2026-08-15T12:00:00Z",
            "deck_count": 0,
            "total_saves_count": 0,
        }
        user_service.get_user_profile.assert_awaited_once_with(
            viewer_id=current_user.id, username="Test-User",
        )

    async def test_returns_404_when_profile_does_not_exist(
        self, client, current_user, user_service,
    ):
        user_service.get_user_profile.side_effect = UserNotFoundError()

        response = await client.get("/users/profile/missing-user")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "code": "USER_NOT_FOUND", "message": "User not found",
        }
        user_service.get_user_profile.assert_awaited_once_with(
            viewer_id=current_user.id, username="missing-user",
        )

    async def test_rejects_too_short_username(self, client, user_service):
        response = await client.get("/users/profile/ab")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [{
                "type": "string_too_short",
                "loc": ["path", "username"],
                "msg": "String should have at least 3 characters",
                "input": "ab",
                "ctx": {"min_length": 3},
            }],
        }
        user_service.get_user_profile.assert_not_awaited()


class TestCreateUser:
    @pytest.mark.parametrize(
        ("service_error", "expected_code", "expected_message"),
        [
            (EmailAlreadyExistsError(), "EMAIL_ALREADY_EXISTS", "Email is already in use"),
            (UsernameAlreadyExistsError(), "USERNAME_ALREADY_EXISTS", "Username is already in use"),
        ],
    )
    async def test_returns_specific_conflict(
        self, client, user_service, service_error, expected_code, expected_message,
    ):
        payload = {
            "username": "new-user", "email": "new@example.com", "password": "password123",
        }
        user_service.create_user.side_effect = service_error

        response = await client.post("/users/create", json=payload)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {"code": expected_code, "message": expected_message}
        user_service.create_user.assert_awaited_once_with(CreateUserRequest(**payload))

    async def test_creates_user(
        self,
        client: AsyncClient,
        user_service: AsyncMock,
    ):
        payload = {
            "username": "new-user",
            "email": "new@example.com",
            "password": "password123",
        }

        new_user = make_user(
            username=payload["username"],
            email=payload["email"],
        )
        user_settings = make_user_settings()

        new_user.settings = user_settings
        user_service.create_user.return_value = new_user

        response = await client.post(
            "/users/create",
            json=payload,
        )

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "new-user",
            "email": "new@example.com",
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == expected

        user_service.create_user.assert_awaited_once_with(CreateUserRequest(**payload))

    async def test_verifies_captcha_header_before_creating_user(
        self,
        client: AsyncClient,
        user_service: AsyncMock,
        captcha_service: AsyncMock,
    ):
        payload = {
            "username": "new-user",
            "email": "new@example.com",
            "password": "password123",
        }
        user_service.create_user.side_effect = UsernameAlreadyExistsError()

        response = await client.post(
            "/users/create",
            json=payload,
            headers={"X-Altcha": "solved-captcha"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        captcha_service.verify.assert_awaited_once_with("solved-captcha")
        user_service.create_user.assert_awaited_once_with(CreateUserRequest(**payload))

    async def test_returns_403_without_creating_user_when_captcha_is_rejected(
        self,
        client: AsyncClient,
        user_service: AsyncMock,
        captcha_service: AsyncMock,
    ):
        payload = {
            "username": "new-user",
            "email": "new@example.com",
            "password": "password123",
        }
        captcha_service.verify.side_effect = CaptchaError()

        response = await client.post("/users/create", json=payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            "code": "CAPTCHA_INVALID",
            "message": "Captcha verification failed",
        }
        captcha_service.verify.assert_awaited_once_with(None)
        user_service.create_user.assert_not_awaited()

    async def test_does_not_verify_captcha_when_ip_limit_is_exceeded(
        self,
        client: AsyncClient,
        captcha_service: AsyncMock,
        redis_rate_limiter: AsyncMock,
    ):
        payload = {
            "username": "new-user",
            "email": "new@example.com",
            "password": "password123",
        }
        redis_rate_limiter.check.return_value = False

        response = await client.post(
            "/users/create",
            json=payload,
            headers={"X-Altcha": "solved-captcha"},
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        captcha_service.verify.assert_not_awaited()

    async def test_normalizes_payload(
        self,
        client: AsyncClient,
        user_service: AsyncMock,
    ):
        payload = {
            "username": "  NeW-UsEr  ",
            "email": "  NEW@EXAMPLE.COM  ",
            "password": "password123",
        }

        new_user = make_user(
            username="NeW-UsEr",
            email="new@example.com",
        )
        user_settings = make_user_settings()

        new_user.settings = user_settings
        user_service.create_user.return_value = new_user

        response = await client.post(
            "/users/create",
            json=payload,
        )

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "NeW-UsEr",
            "email": "new@example.com",
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == expected

        user_service.create_user.assert_awaited_once_with(
            CreateUserRequest(
                username="NeW-UsEr",
                email="new@example.com",
                password="password123",
            )
        )

    @pytest.mark.parametrize(
        ("payload", "expected_username", "expected_password"),
        [
            pytest.param(
                {
                    "username": "abc",
                    "email": "user@example.com",
                    "password": "password123",
                },
                "abc",
                "password123",
                id="username_minimum_length",
            ),
            pytest.param(
                {
                    "username": "a" * 18,
                    "email": "user@example.com",
                    "password": "password123",
                },
                "a" * 18,
                "password123",
                id="username_maximum_length",
            ),
            pytest.param(
                {
                    "username": "username",
                    "email": "user@example.com",
                    "password": "a" * 8,
                },
                "username",
                "a" * 8,
                id="password_minimum_length",
            ),
            pytest.param(
                {
                    "username": "username",
                    "email": "user@example.com",
                    "password": "a" * 128,
                },
                "username",
                "a" * 128,
                id="password_maximum_length",
            ),
        ],
    )
    async def test_accepts_boundary_payload(
        self,
        client: AsyncClient,
        payload,
        expected_username,
        expected_password,
        user_service: AsyncMock,
    ):
        new_user = make_user(
            username=expected_username,
            email="user@example.com",
        )
        user_settings = make_user_settings()
        new_user.settings = user_settings
        user_service.create_user.return_value = new_user

        response = await client.post(
            "/users/create",
            json=payload,
        )

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": expected_username,
            "email": "user@example.com",
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == expected

        user_service.create_user.assert_awaited_once_with(
            CreateUserRequest(
                username=expected_username,
                email="user@example.com",
                password=expected_password,
            )
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {
                    "username": "ab",
                    "email": "user@example.com",
                    "password": "password123",
                },
                {
                    "type": "string_too_short",
                    "loc": ["body", "username"],
                    "msg": "String should have at least 3 characters",
                    "input": "ab",
                    "ctx": {"min_length": 3},
                },
                id="username_too_short",
            ),
            pytest.param(
                {
                    "username": "a" * 19,
                    "email": "user@example.com",
                    "password": "password123",
                },
                {
                    "type": "string_too_long",
                    "loc": ["body", "username"],
                    "msg": "String should have at most 18 characters",
                    "input": "a" * 19,
                    "ctx": {"max_length": 18},
                },
                id="username_too_long",
            ),
            pytest.param(
                {
                    "username": "user name",
                    "email": "user@example.com",
                    "password": "password123",
                },
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["body", "username"],
                    "msg": "String should match pattern '^[A-Za-z0-9_-]+$'",
                    "input": "user name",
                    "ctx": {"pattern": r"^[A-Za-z0-9_-]+$"},
                },
                id="username_contains_spaces",
            ),
            pytest.param(
                {
                    "username": "username",
                    "email": "not-an-email",
                    "password": "password123",
                },
                {
                    "type": "value_error",
                    "loc": ["body", "email"],
                    "msg": (
                        "value is not a valid email address: An email "
                        "address must have an @-sign."
                    ),
                    "input": "not-an-email",
                    "ctx": {"reason": "An email address must have an @-sign."},
                },
                id="email_invalid",
            ),
            pytest.param(
                {
                    "username": "username",
                    "email": "user@example.com",
                    "password": "short",
                },
                {
                    "type": "string_too_short",
                    "loc": ["body", "password"],
                    "msg": "String should have at least 8 characters",
                    "input": "short",
                    "ctx": {"min_length": 8},
                },
                id="password_too_short",
            ),
            pytest.param(
                {
                    "username": "username",
                    "email": "user@example.com",
                    "password": "a" * 129,
                },
                {
                    "type": "string_too_long",
                    "loc": ["body", "password"],
                    "msg": "String should have at most 128 characters",
                    "input": "a" * 129,
                    "ctx": {"max_length": 128},
                },
                id="password_too_long",
            ),
            pytest.param(
                {
                    "username": "username",
                    "email": "user@example.com",
                    "password": "password with spaces",
                },
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["body", "password"],
                    "msg": "String should match pattern '^\\S+$'",
                    "input": "password with spaces",
                    "ctx": {"pattern": r"^\S+$"},
                },
                id="password_contains_spaces",
            ),
        ],
    )
    async def test_rejects_invalid_payload(
        self,
        client: AsyncClient,
        payload,
        expected_detail,
        user_service: AsyncMock,
    ):
        response = await client.post(
            "/users/create",
            json=payload,
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        user_service.create_user.assert_not_awaited()

    @pytest.mark.parametrize(
        ("payload", "expected_details"),
        [
            pytest.param(
                {
                    "email": "user@example.com",
                    "password": "password123",
                },
                [
                    {
                        "type": "missing",
                        "loc": ["body", "username"],
                        "msg": "Field required",
                        "input": {
                            "email": "user@example.com",
                            "password": "password123",
                        },
                    }
                ],
                id="username_missing",
            ),
            pytest.param(
                {
                    "username": "username",
                    "password": "password123",
                },
                [
                    {
                        "type": "missing",
                        "loc": ["body", "email"],
                        "msg": "Field required",
                        "input": {
                            "username": "username",
                            "password": "password123",
                        },
                    }
                ],
                id="email_missing",
            ),
            pytest.param(
                {
                    "username": "username",
                    "email": "user@example.com",
                },
                [
                    {
                        "type": "missing",
                        "loc": ["body", "password"],
                        "msg": "Field required",
                        "input": {
                            "username": "username",
                            "email": "user@example.com",
                        },
                    }
                ],
                id="password_missing",
            ),
            pytest.param(
                {},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "username"],
                        "msg": "Field required",
                        "input": {},
                    },
                    {
                        "type": "missing",
                        "loc": ["body", "email"],
                        "msg": "Field required",
                        "input": {},
                    },
                    {
                        "type": "missing",
                        "loc": ["body", "password"],
                        "msg": "Field required",
                        "input": {},
                    },
                ],
                id="all_fields_missing",
            ),
        ],
    )
    async def test_rejects_missing_fields(
        self,
        client: AsyncClient,
        payload,
        expected_details,
        user_service: AsyncMock,
    ):
        response = await client.post(
            "/users/create",
            json=payload,
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": expected_details,
        }

        user_service.create_user.assert_not_awaited()


class TestUpdateUser:
    async def test_updates_current_user(
        self,
        client: AsyncClient,
        current_user,
        user_service: AsyncMock,
    ):
        payload = {
            "username": "updated-user",
            "email": "updated@example.com",
        }
        updated_user = make_user(
            username="updated-user",
            email="updated@example.com",
            settings=make_user_settings(
                locale="en-US",
                theme="dark",
                show_previews_for_long=False,
            ),
        )
        user_service.update_user.return_value = updated_user

        response = await client.patch(
            "/users/me",
            json=payload,
        )

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "updated-user",
            "email": "updated@example.com",
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "en-US",
                "theme": "dark",
                "show_previews_for_long": False,
            },
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        user_service.update_user.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UpdateUserRequest(**payload),
        )

    @pytest.mark.parametrize(
        ("payload", "expected_username", "expected_email"),
        [
            pytest.param(
                {"username": "renamed-user"},
                "renamed-user",
                "test@example.com",
                id="username_only",
            ),
            pytest.param(
                {"email": "renamed@example.com"},
                "test-user",
                "renamed@example.com",
                id="email_only",
            ),
        ],
    )
    async def test_updates_single_field(
        self,
        client: AsyncClient,
        current_user,
        payload,
        expected_username,
        expected_email,
        user_service: AsyncMock,
    ):
        updated_user = make_user(
            username=expected_username,
            email=expected_email,
            settings=make_user_settings(),
        )
        user_service.update_user.return_value = updated_user

        response = await client.patch(
            "/users/me",
            json=payload,
        )

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": expected_username,
            "email": expected_email,
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        user_service.update_user.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UpdateUserRequest(**payload),
        )

    @pytest.mark.parametrize(
        (
            "payload",
            "expected_username",
            "expected_email",
            "expected_service_payload",
        ),
        [
            pytest.param(
                {
                    "username": "  ReNaMeD-UsEr  ",
                    "email": "  RENAMED@EXAMPLE.COM  ",
                },
                "ReNaMeD-UsEr",
                "renamed@example.com",
                {
                    "username": "ReNaMeD-UsEr",
                    "email": "renamed@example.com",
                },
                id="strips_whitespace_and_lowercases",
            ),
            pytest.param(
                {"username": "abc"},
                "abc",
                "test@example.com",
                {"username": "abc"},
                id="username_minimum_length",
            ),
            pytest.param(
                {"username": "a" * 18},
                "a" * 18,
                "test@example.com",
                {"username": "a" * 18},
                id="username_maximum_length",
            ),
        ],
    )
    async def test_passes_normalized_and_boundary_payload(
        self,
        client: AsyncClient,
        current_user,
        payload,
        expected_username,
        expected_email,
        expected_service_payload,
        user_service: AsyncMock,
    ):
        updated_user = make_user(
            username=expected_username,
            email=expected_email,
            settings=make_user_settings(),
        )
        user_service.update_user.return_value = updated_user

        response = await client.patch(
            "/users/me",
            json=payload,
        )

        expected = {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": expected_username,
            "email": expected_email,
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T13:00:00Z",
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        user_service.update_user.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UpdateUserRequest(**expected_service_payload),
        )

    @pytest.mark.parametrize(
        ("payload", "expected_details"),
        [
            pytest.param(
                {"username": "ab"},
                [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "username", "constrained-str"],
                        "msg": "String should have at least 3 characters",
                        "input": "ab",
                        "ctx": {"min_length": 3},
                    },
                    {
                        "type": "none_required",
                        "loc": ["body", "username", "none"],
                        "msg": "Input should be None",
                        "input": "ab",
                    },
                ],
                id="username_too_short",
            ),
            pytest.param(
                {"username": "a" * 19},
                [
                    {
                        "type": "string_too_long",
                        "loc": ["body", "username", "constrained-str"],
                        "msg": "String should have at most 18 characters",
                        "input": "a" * 19,
                        "ctx": {"max_length": 18},
                    },
                    {
                        "type": "none_required",
                        "loc": ["body", "username", "none"],
                        "msg": "Input should be None",
                        "input": "a" * 19,
                    },
                ],
                id="username_too_long",
            ),
            pytest.param(
                {"username": "user name"},
                [
                    {
                        "type": "string_pattern_mismatch",
                        "loc": ["body", "username", "constrained-str"],
                        "msg": "String should match pattern '^[A-Za-z0-9_-]+$'",
                        "input": "user name",
                        "ctx": {"pattern": r"^[A-Za-z0-9_-]+$"},
                    },
                    {
                        "type": "none_required",
                        "loc": ["body", "username", "none"],
                        "msg": "Input should be None",
                        "input": "user name",
                    },
                ],
                id="username_contains_spaces",
            ),
            pytest.param(
                {"email": "not-an-email"},
                [
                    {
                        "type": "value_error",
                        "loc": ["body", "email", (
                            "chain[function-after[functools.partial(<function max_length_validator at <address>>, max_length=255)(), "
                            "function-after[functools.partial(<function min_length_validator at <address>>, min_length=1)(), "
                            "function-after[_validate(), str]]],function-wrap[_apply_constraint_with_incompatibility_info()],"
                            "function-wrap[_apply_constraint_with_incompatibility_info()]]"
                        )],
                        "msg": (
                            "value is not a valid email address: An email "
                            "address must have an @-sign."
                        ),
                        "input": "not-an-email",
                        "ctx": {"reason": "An email address must have an @-sign."},
                    },
                    {
                        "type": "none_required",
                        "loc": ["body", "email", "none"],
                        "msg": "Input should be None",
                        "input": "not-an-email",
                    },
                ],
                id="email_invalid",
            ),
        ],
    )
    async def test_rejects_invalid_payload(
        self, client: AsyncClient, payload, expected_details, user_service: AsyncMock,
    ):
        response = await client.patch("/users/me", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        body = response.json()
        if "email" in payload:
            # Pydantic includes process-specific function addresses in this union label.
            branch = body["details"][0]["loc"][2]
            assert len(re.findall(r"0x[0-9a-f]+", branch)) == 2
            body["details"][0]["loc"][2] = re.sub(r"0x[0-9a-f]+", "<address>", branch)
        assert body == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": expected_details,
        }
        user_service.update_user.assert_not_awaited()

    async def test_returns_422_when_update_body_is_empty(
        self, client: AsyncClient, current_user, user_service: AsyncMock,
    ):
        user_service.update_user.side_effect = RequestValueError(
            message="Update body is empty", failed_field="body",
        )

        response = await client.patch("/users/me", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "value_error",
                    "loc": ["body", "body"],
                    "msg": "Update body is empty",
                    "input": None,
                },
            ],
        }
        user_service.update_user.assert_awaited_once_with(
            current_user_id=current_user.id, payload=UpdateUserRequest(),
        )

    @pytest.mark.parametrize(
        ("payload", "field"),
        [
            ({"username": None}, "username"),
            ({"email": None}, "email"),
            ({"username": None, "email": None}, "username"),
            ({"username": "valid-name", "email": None}, "email"),
        ],
    )
    async def test_rejects_null_before_calling_service(
        self, client: AsyncClient, user_service: AsyncMock, payload, field,
    ):
        response = await client.patch("/users/me", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "value_error", "loc": ["body", field],
                    "msg": "Field must not be null", "input": None,
                },
            ],
        }
        user_service.update_user.assert_not_awaited()

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                UserNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "USER_NOT_FOUND",
                "User not found",
                id="user_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "USER_PERMISSION_DENIED",
                "Permission denied",
                id="permission_denied",
            ),
            pytest.param(
                UserAlreadyExistsError(),
                status.HTTP_409_CONFLICT,
                "USER_ALREADY_EXISTS",
                "Username or email is already in use",
                id="username_or_email_conflict",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        user_service: AsyncMock,
    ):
        payload = {"username": "updated-user"}
        user_service.update_user.side_effect = service_error

        response = await client.patch(
            "/users/me",
            json=payload,
        )

        assert response.status_code == expected_status
        assert response.json() == {"code": expected_code, "message": expected_message}

        user_service.update_user.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UpdateUserRequest(**payload),
        )


class TestDeleteUser:
    async def test_deletes_current_user_and_clears_auth_cookies(
        self,
        client: AsyncClient,
        current_user,
        user_service: AsyncMock,
    ):
        response = await client.delete("/users/me")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        set_cookie_headers = response.headers.get_list("set-cookie")
        cookies = SimpleCookie()
        cookies.load(set_cookie_headers[0])
        cookies.load(set_cookie_headers[1])

        assert len(set_cookie_headers) == 2
        assert set(cookies) == {"access_token", "refresh_token"}

        access_token = cookies["access_token"]
        assert access_token.value == ""
        assert access_token["max-age"] == "0"
        assert access_token["path"] == "/"
        assert access_token["secure"] is True
        assert access_token["httponly"] is True
        assert access_token["samesite"] == "lax"
        assert access_token["expires"]

        refresh_token = cookies["refresh_token"]
        assert refresh_token.value == ""
        assert refresh_token["max-age"] == "0"
        assert refresh_token["path"] == "/"
        assert refresh_token["secure"] is True
        assert refresh_token["httponly"] is True
        assert refresh_token["samesite"] == "lax"
        assert refresh_token["expires"]

        user_service.delete_user.assert_awaited_once_with(
            current_user_id=current_user.id,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_code", "expected_message"),
        [
            pytest.param(
                UserNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "USER_NOT_FOUND",
                "User not found",
                id="user_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "USER_PERMISSION_DENIED",
                "Permission denied",
                id="permission_denied",
            ),
        ],
    )
    async def test_returns_service_error_without_clearing_cookies(
        self,
        client: AsyncClient,
        current_user,
        service_error,
        expected_status,
        expected_code,
        expected_message,
        user_service: AsyncMock,
    ):
        user_service.delete_user.side_effect = service_error

        response = await client.delete("/users/me")

        assert response.status_code == expected_status
        assert response.json() == {"code": expected_code, "message": expected_message}
        assert response.headers.get_list("set-cookie") == []

        user_service.delete_user.assert_awaited_once_with(
            current_user_id=current_user.id,
        )


class TestGetPublicDecksByUser:
    async def test_returns_public_decks_for_authenticated_viewer(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_public_by_owner_uuid.return_value = CursorPage(
            items=[deck],
            next_cursor="next-page-cursor",
            has_more=True,
        )

        response = await client.get(f"/users/{user.uuid}/decks")

        expected = {
            "items": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "owner_uuid": ("0198ad01-b200-7000-8000-000000000042"),
                    "owner_username": "test-user",
                    "title": "Test deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                }
            ],
            "next_cursor": "next-page-cursor",
            "has_more": True,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        deck_service.get_public_by_owner_uuid.assert_awaited_once_with(
            owner_uuid=user.uuid,
            viewer_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=30,
        )

    @pytest.mark.parametrize("optional_current_user", [None], indirect=True)
    async def test_returns_public_decks_for_anonymous_viewer(
        self,
        client: AsyncClient,
        optional_current_user,
        deck,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_public_by_owner_uuid.return_value = CursorPage(
            items=[deck],
            next_cursor=None,
            has_more=False,
        )

        response = await client.get(f"/users/{user.uuid}/decks")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [
                {
                    "uuid": "0198ad01-b200-7000-8000-000000000200",
                    "title": "Test deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "owner_uuid": "0198ad01-b200-7000-8000-000000000042",
                    "owner_username": "test-user",
                    "updated_at": "2026-08-15T15:00:00Z",
                },
            ],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_public_by_owner_uuid.assert_awaited_once_with(
            owner_uuid=user.uuid,
            viewer_id=None,
            search_query=None,
            cursor=None,
            limit=30,
        )

    async def test_returns_empty_page(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_public_by_owner_uuid.return_value = CursorPage(
            items=[],
            next_cursor=None,
            has_more=False,
        )

        response = await client.get(f"/users/{user.uuid}/decks")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_public_by_owner_uuid.assert_awaited_once_with(
            owner_uuid=user.uuid,
            viewer_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=30,
        )

    @pytest.mark.parametrize(
        ("raw_query", "normalized_query"),
        [
            pytest.param("english", "english", id="unchanged"),
            pytest.param(
                "  EnGliSh Words  ",
                "english words",
                id="strips_whitespace_and_lowercases",
            ),
            pytest.param("a", "a", id="minimum_length"),
            pytest.param(
                "a" * 50,
                "a" * 50,
                id="maximum_length",
            ),
        ],
    )
    async def test_passes_normalized_search_query(
        self,
        client: AsyncClient,
        current_user,
        raw_query,
        normalized_query,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_public_by_owner_uuid.return_value = CursorPage(
            items=[],
            next_cursor=None,
            has_more=False,
        )

        response = await client.get(
            f"/users/{user.uuid}/decks",
            params={"q": raw_query},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_public_by_owner_uuid.assert_awaited_once_with(
            owner_uuid=user.uuid,
            viewer_id=current_user.id,
            search_query=normalized_query,
            cursor=None,
            limit=30,
        )

    @pytest.mark.parametrize(
        ("limit", "cursor"),
        [
            pytest.param(50, "some-cursor", id="ordinary_values"),
            pytest.param(1, "some-cursor", id="minimum_limit"),
            pytest.param(100, "some-cursor", id="maximum_limit"),
            pytest.param(30, "a" * 512, id="maximum_cursor_length"),
        ],
    )
    async def test_passes_pagination_params(
        self,
        client: AsyncClient,
        current_user,
        limit,
        cursor,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_public_by_owner_uuid.return_value = CursorPage(
            items=[],
            next_cursor=None,
            has_more=False,
        )

        response = await client.get(
            f"/users/{user.uuid}/decks",
            params={
                "limit": limit,
                "cursor": cursor,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_public_by_owner_uuid.assert_awaited_once_with(
            owner_uuid=user.uuid,
            viewer_id=current_user.id,
            search_query=None,
            cursor=cursor,
            limit=limit,
        )

    async def test_returns_404_when_user_not_found(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_public_by_owner_uuid.side_effect = UserNotFoundError()

        response = await client.get(f"/users/{user.uuid}/decks")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"code": "USER_NOT_FOUND", "message": "User not found"}

        deck_service.get_public_by_owner_uuid.assert_awaited_once_with(
            owner_uuid=user.uuid,
            viewer_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=30,
        )

    async def test_rejects_invalid_user_uuid(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.get("/users/not-a-uuid/decks")

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "user_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == expected

        deck_service.get_public_by_owner_uuid.assert_not_awaited()


    @pytest.mark.parametrize(
        ("limit", "expected_detail"),
        [
            pytest.param(
                0,
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="below_minimum",
            ),
            pytest.param(
                101,
                {
                    "type": "less_than_equal",
                    "loc": ["query", "limit"],
                    "msg": "Input should be less than or equal to 100",
                    "input": "101",
                    "ctx": {"le": 100},
                },
                id="above_maximum",
            ),
        ],
    )
    async def test_rejects_invalid_limit(
        self,
        client: AsyncClient,
        limit,
        expected_detail,
        deck_service: AsyncMock,
    ):
        user = make_user()

        response = await client.get(
            f"/users/{user.uuid}/decks",
            params={"limit": limit},
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_public_by_owner_uuid.assert_not_awaited()

    @pytest.mark.parametrize(
        ("search_query", "expected_detail"),
        [
            pytest.param(
                " ",
                {
                    "type": "string_too_short",
                    "loc": ["query", "q"],
                    "msg": "String should have at least 1 character",
                    "input": " ",
                    "ctx": {"min_length": 1},
                },
                id="empty_after_normalization",
            ),
            pytest.param(
                "a" * 51,
                {
                    "type": "string_too_long",
                    "loc": ["query", "q"],
                    "msg": "String should have at most 50 characters",
                    "input": "a" * 51,
                    "ctx": {"max_length": 50},
                },
                id="above_maximum_length",
            ),
        ],
    )
    async def test_rejects_invalid_search_query(
        self,
        client: AsyncClient,
        search_query,
        expected_detail,
        deck_service: AsyncMock,
    ):
        user = make_user()

        response = await client.get(
            f"/users/{user.uuid}/decks",
            params={"q": search_query},
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_public_by_owner_uuid.assert_not_awaited()

    async def test_rejects_too_long_cursor(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        user = make_user()
        cursor = "a" * 513

        response = await client.get(
            f"/users/{user.uuid}/decks",
            params={"cursor": cursor},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "string_too_long",
                    "loc": ["query", "cursor"],
                    "msg": "String should have at most 512 characters",
                    "input": cursor,
                    "ctx": {"max_length": 512},
                }
            ],
        }

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == expected

        deck_service.get_public_by_owner_uuid.assert_not_awaited()


class TestUserAuthentication:
    @pytest.mark.parametrize(
        ("method", "path", "payload"),
        [
            ("GET", "/users/me", None),
            ("PATCH", "/users/me", {"username": "updated-user"}),
            ("DELETE", "/users/me", None),
            ("PATCH", "/users/me/settings", {"theme": "dark"}),
            ("GET", "/users/me/daily-activity?from_datetime=2020-01-01T00:00:00Z", None),
            ("GET", "/users/me/decks", None),
            ("GET", "/users/me/training-sessions", None),
            ("GET", "/users/me/decks/saved", None),
        ],
    )
    @pytest.mark.parametrize(
        ("auth_error", "expected"),
        [
            (AccessTokenNotFoundError(), {"code": "ACCESS_TOKEN_NOT_FOUND", "message": "Not authorized"}),
            (InvalidTokenError(), {"code": "INVALID_TOKEN", "message": "Invalid token"}),
        ],
        ids=["missing_token", "invalid_token"],
    )
    async def test_rejects_unauthorized_requests_before_calling_services(
        self, app, client, monkeypatch, user_service, deck_service,
        user_deck_service, training_session_service, method, path, payload,
        auth_error, expected,
    ):
        async def reject_user():
            raise auth_error

        monkeypatch.setitem(app.dependency_overrides, get_current_user, reject_user)
        monkeypatch.setitem(app.dependency_overrides, get_current_user_with_settings, reject_user)

        response = await client.request(method, path, json=payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == expected
        assert response.headers.get_list("set-cookie") == []
        assert user_service.mock_calls == []
        assert deck_service.mock_calls == []
        assert user_deck_service.mock_calls == []
        assert training_session_service.mock_calls == []
