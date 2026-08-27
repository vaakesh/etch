from datetime import UTC, date, datetime, timedelta, timezone
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from app.decks.schemas import (
    DeckListItemResponse,
    DeckResponse,
    DeckViewerStateResponse,
)
from app.errors import RequestValueError
from app.training_sessions.models import TrainingSessionStatus
from app.users.errors import (
    PermissionDeniedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.users.schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    UserSettingsUpdate,
)
from tests.unit.factories import (
    make_card,
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
        current_user,
        user_settings,
        user_service: AsyncMock,
    ):
        user_service.get_user_settings_by_id.return_value = user_settings

        response = await client.get("/users/me")

        expected = {
            "uuid": "12345678-1234-5678-1234-567812345678",
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

        user_service.get_user_settings_by_id.assert_awaited_once_with(
            user_id=current_user.id,
            for_update=False,
        )

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
        current_user,
        user_settings,
        user_service: AsyncMock,
    ):
        user_service.get_user_settings_by_id.return_value = user_settings

        response = await client.get("/users/me")

        expected = {
            "uuid": "12345678-1234-5678-1234-567812345678",
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

        user_service.get_user_settings_by_id.assert_awaited_once_with(
            user_id=current_user.id,
            for_update=False,
        )


class TestGetUserDailyActivity:
    async def test_returns_daily_activity_from_date(
        self,
        client: AsyncClient,
        current_user,
        training_session_service: AsyncMock,
    ):
        training_session_service.user_daily_activity.return_value = {
            date(2026, 8, 1): 2,
            date(2026, 8, 3): 5,
        }

        response = await client.get(
            "/users/me/daily-activity",
            params={"from_date": "2026-08-01T00:00:00Z"},
        )

        expected = {
            "2026-08-01": 2,
            "2026-08-03": 5,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.user_daily_activity.assert_awaited_once_with(
            user_id=current_user.id,
            from_date=datetime(2026, 8, 1, tzinfo=UTC),
            to_date=None,
        )

    async def test_passes_date_range_and_returns_empty_activity(
        self,
        client: AsyncClient,
        current_user,
        training_session_service: AsyncMock,
    ):
        training_session_service.user_daily_activity.return_value = {}

        response = await client.get(
            "/users/me/daily-activity",
            params={
                "from_date": "2026-08-01T10:30:00+03:00",
                "to_date": "2026-08-31T23:59:59+03:00",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {}

        training_session_service.user_daily_activity.assert_awaited_once_with(
            user_id=current_user.id,
            from_date=datetime(
                2026,
                8,
                1,
                10,
                30,
                tzinfo=timezone(timedelta(hours=3)),
            ),
            to_date=datetime(
                2026,
                8,
                31,
                23,
                59,
                59,
                tzinfo=timezone(timedelta(hours=3)),
            ),
        )

    async def test_rejects_missing_from_date(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        response = await client.get("/users/me/daily-activity")

        expected = {
            "message": "Validation error",
            "details": [
                {
                    "type": "missing",
                    "loc": ["query", "from_date"],
                    "msg": "Field required",
                    "input": None,
                }
            ],
        }

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == expected

        training_session_service.user_daily_activity.assert_not_awaited()

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            pytest.param(
                {"from_date": "not-a-date"},
                "from_date",
                id="from_date_invalid",
            ),
            pytest.param(
                {
                    "from_date": "2026-08-01T00:00:00Z",
                    "to_date": "not-a-date",
                },
                "to_date",
                id="to_date_invalid",
            ),
        ],
    )
    async def test_rejects_invalid_date(
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

        training_session_service.user_daily_activity.assert_not_awaited()


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
            payload=UserSettingsUpdate(**payload),
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
            payload=UserSettingsUpdate(**payload),
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
            payload=UserSettingsUpdate(**payload),
        )


class TestChangePassword:
    async def test_changes_password(
        self,
        client: AsyncClient,
        current_user,
        auth_service: AsyncMock,
    ):
        payload = {
            "current_password": "old-password",
            "new_password": "new-password",
        }

        response = await client.put(
            "/users/me/password",
            json=payload,
        )

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

        auth_service.change_password.assert_awaited_once_with(
            user_id=current_user.id,
            current_password=payload["current_password"],
            new_password=payload["new_password"],
        )

    @pytest.mark.parametrize(
        ("payload", "expected_details"),
        [
            pytest.param(
                {
                    "current_password": "short",
                    "new_password": "new-password",
                },
                [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "current_password"],
                        "msg": "String should have at least 8 characters",
                        "input": "short",
                        "ctx": {"min_length": 8},
                    }
                ],
                id="current_password_too_short",
            ),
            pytest.param(
                {
                    "current_password": "old-password",
                    "new_password": "short",
                },
                [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "new_password"],
                        "msg": "String should have at least 8 characters",
                        "input": "short",
                        "ctx": {"min_length": 8},
                    }
                ],
                id="new_password_too_short",
            ),
            pytest.param(
                {
                    "current_password": "old password",
                    "new_password": "new-password",
                },
                [
                    {
                        "type": "string_pattern_mismatch",
                        "loc": ["body", "current_password"],
                        "msg": "String should match pattern '^\\S+$'",
                        "input": "old password",
                        "ctx": {"pattern": r"^\S+$"},
                    }
                ],
                id="current_password_contains_spaces",
            ),
            pytest.param(
                {
                    "current_password": "old-password",
                    "new_password": "new password",
                },
                [
                    {
                        "type": "string_pattern_mismatch",
                        "loc": ["body", "new_password"],
                        "msg": "String should match pattern '^\\S+$'",
                        "input": "new password",
                        "ctx": {"pattern": r"^\S+$"},
                    }
                ],
                id="new_password_contains_spaces",
            ),
            pytest.param(
                {
                    "current_password": "",
                    "new_password": "new-password",
                },
                [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "current_password"],
                        "msg": "String should have at least 8 characters",
                        "input": "",
                        "ctx": {"min_length": 8},
                    }
                ],
                id="current_password_empty",
            ),
            pytest.param(
                {
                    "current_password": "old-password",
                    "new_password": "",
                },
                [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "new_password"],
                        "msg": "String should have at least 8 characters",
                        "input": "",
                        "ctx": {"min_length": 8},
                    }
                ],
                id="new_password_empty",
            ),
        ],
    )
    async def test_rejects_invalid_password(
        self,
        client: AsyncClient,
        payload,
        expected_details,
        auth_service: AsyncMock,
    ):
        response = await client.put(
            "/users/me/password",
            json=payload,
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "message": "Validation error",
            "details": expected_details,
        }

        auth_service.change_password.assert_not_awaited()

    @pytest.mark.parametrize(
        ("payload", "expected_details"),
        [
            pytest.param(
                {"new_password": "new-password"},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "current_password"],
                        "msg": "Field required",
                        "input": {"new_password": "new-password"},
                    }
                ],
                id="current_password_missing",
            ),
            pytest.param(
                {"current_password": "old-password"},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "new_password"],
                        "msg": "Field required",
                        "input": {"current_password": "old-password"},
                    }
                ],
                id="new_password_missing",
            ),
            pytest.param(
                {},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "current_password"],
                        "msg": "Field required",
                        "input": {},
                    },
                    {
                        "type": "missing",
                        "loc": ["body", "new_password"],
                        "msg": "Field required",
                        "input": {},
                    },
                ],
                id="all_passwords_missing",
            ),
        ],
    )
    async def test_rejects_missing_password(
        self,
        client: AsyncClient,
        payload,
        expected_details,
        auth_service: AsyncMock,
    ):
        response = await client.put(
            "/users/me/password",
            json=payload,
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "message": "Validation error",
            "details": expected_details,
        }

        auth_service.change_password.assert_not_awaited()


class TestGetMyDecks:
    async def test_returns_current_user_decks(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        deck_service.get_all_by_user_uuid.return_value = (
            [deck],
            None,
            False,
        )

        response = await client.get("/users/me/decks")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": ("12345678-1234-5678-1234-567812345678"),
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

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=current_user.uuid,
            search_query=None,
            cursor=None,
            limit=30,
            public_only=False,
            current_user_id=current_user.id,
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

        deck_service.get_all_by_user_uuid.return_value = (
            decks,
            None,
            False,
        )

        response = await client.get("/users/me/decks")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": ("12345678-1234-5678-1234-567812345678"),
                    "title": "First deck",
                    "description": "Test deck description",
                    "words_count": 10,
                    "is_public": True,
                    "saves_count": 5,
                    "updated_at": "2026-08-15T15:00:00Z",
                },
                {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": ("12345678-1234-5678-1234-567812345678"),
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

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=current_user.uuid,
            search_query=None,
            cursor=None,
            limit=30,
            public_only=False,
            current_user_id=current_user.id,
        )

    async def test_returns_empty_page(
        self,
        client: AsyncClient,
        current_user,
        deck_service: AsyncMock,
    ):
        deck_service.get_all_by_user_uuid.return_value = (
            [],
            None,
            False,
        )

        response = await client.get("/users/me/decks")

        assert response.status_code == status.HTTP_200_OK

        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=current_user.uuid,
            search_query=None,
            cursor=None,
            limit=30,
            public_only=False,
            current_user_id=current_user.id,
        )

    async def test_returns_next_cursor(
        self,
        client: AsyncClient,
        current_user,
        deck,
        deck_service: AsyncMock,
    ):
        next_cursor = "next-page-cursor"

        deck_service.get_all_by_user_uuid.return_value = (
            [deck],
            next_cursor,
            True,
        )

        response = await client.get("/users/me/decks")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": ("12345678-1234-5678-1234-567812345678"),
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

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=current_user.uuid,
            search_query=None,
            cursor=None,
            limit=30,
            public_only=False,
            current_user_id=current_user.id,
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
        deck_service.get_all_by_user_uuid.return_value = (
            [],
            None,
            False,
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

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=current_user.uuid,
            search_query=None,
            cursor=cursor,
            limit=limit,
            public_only=False,
            current_user_id=current_user.id,
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
        deck_service.get_all_by_user_uuid.return_value = (
            [],
            None,
            False,
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

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=current_user.uuid,
            search_query=normalized_query,
            cursor=None,
            limit=30,
            public_only=False,
            current_user_id=current_user.id,
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
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_all_by_user_uuid.assert_not_awaited()

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
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_all_by_user_uuid.assert_not_awaited()

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

        deck_service.get_all_by_user_uuid.assert_not_awaited()


class TestGetMyCards:
    async def test_returns_current_user_cards(
        self,
        client: AsyncClient,
        current_user,
        card,
        card_service: AsyncMock,
    ):
        card_service.get_all_by_user_id.return_value = (
            [card],
            None,
            False,
        )

        response = await client.get("/users/me/cards")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "front_text": "привет",
                    "back_text": "hello",
                    "front_lang": "ru",
                    "back_lang": "en",
                    "updated_at": "2026-08-15T15:00:00Z",
                }
            ],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.json() == expected

        card_service.get_all_by_user_id.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=50,
        )

    async def test_returns_multiple_cards(
        self,
        client: AsyncClient,
        current_user,
        card_service: AsyncMock,
    ):
        cards = [
            make_card(
                front_text="first",
                back_text="первый",
            ),
            make_card(
                front_text="second",
                back_text="второй",
            ),
        ]

        card_service.get_all_by_user_id.return_value = (
            cards,
            None,
            False,
        )

        response = await client.get("/users/me/cards")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "front_text": "first",
                    "back_text": "первый",
                    "front_lang": "ru",
                    "back_lang": "en",
                    "updated_at": "2026-08-15T15:00:00Z",
                },
                {
                    "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "front_text": "second",
                    "back_text": "второй",
                    "front_lang": "ru",
                    "back_lang": "en",
                    "updated_at": "2026-08-15T15:00:00Z",
                },
            ],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.json() == expected

        card_service.get_all_by_user_id.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=50,
        )

    async def test_returns_empty_page(
        self,
        client: AsyncClient,
        current_user,
        card_service: AsyncMock,
    ):
        card_service.get_all_by_user_id.return_value = (
            [],
            None,
            False,
        )

        response = await client.get("/users/me/cards")

        assert response.status_code == status.HTTP_200_OK

        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        card_service.get_all_by_user_id.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=50,
        )

    async def test_returns_next_cursor(
        self,
        client: AsyncClient,
        current_user,
        card,
        card_service: AsyncMock,
    ):
        next_cursor = "next-page-cursor"

        card_service.get_all_by_user_id.return_value = (
            [card],
            next_cursor,
            True,
        )

        response = await client.get("/users/me/cards")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "front_text": "привет",
                    "back_text": "hello",
                    "front_lang": "ru",
                    "back_lang": "en",
                    "updated_at": "2026-08-15T15:00:00Z",
                }
            ],
            "next_cursor": next_cursor,
            "has_more": True,
        }

        assert response.json() == expected

        card_service.get_all_by_user_id.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=None,
            cursor=None,
            limit=50,
        )

    @pytest.mark.parametrize(
        ("limit", "cursor"),
        [
            pytest.param(25, "some-cursor", id="ordinary_values"),
            pytest.param(1, "some-cursor", id="minimum_limit"),
            pytest.param(100, "some-cursor", id="maximum_limit"),
            pytest.param(50, "a" * 512, id="maximum_cursor_length"),
        ],
    )
    async def test_passes_pagination_params(
        self,
        client: AsyncClient,
        current_user,
        limit,
        cursor,
        card_service: AsyncMock,
    ):
        card_service.get_all_by_user_id.return_value = (
            [],
            None,
            False,
        )

        response = await client.get(
            "/users/me/cards",
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

        card_service.get_all_by_user_id.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=None,
            cursor=cursor,
            limit=limit,
        )

    @pytest.mark.parametrize(
        ("raw_query", "normalized_query"),
        [
            pytest.param(
                "hello",
                "hello",
                id="unchanged",
            ),
            pytest.param(
                "  HeLLo WoRLd  ",
                "hello world",
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
        card_service: AsyncMock,
    ):
        card_service.get_all_by_user_id.return_value = (
            [],
            None,
            False,
        )

        response = await client.get(
            "/users/me/cards",
            params={"q": raw_query},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        card_service.get_all_by_user_id.assert_awaited_once_with(
            user_id=current_user.id,
            search_query=normalized_query,
            cursor=None,
            limit=50,
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
        card_service: AsyncMock,
    ):
        response = await client.get(
            "/users/me/cards",
            params={
                "limit": limit,
            },
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
        }

        card_service.get_all_by_user_id.assert_not_awaited()

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
        card_service: AsyncMock,
    ):
        response = await client.get(
            "/users/me/cards",
            params={
                "q": search_query,
            },
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
        }

        card_service.get_all_by_user_id.assert_not_awaited()

    async def test_rejects_too_long_cursor(
        self,
        client: AsyncClient,
        card_service: AsyncMock,
    ):
        cursor = "a" * 513

        response = await client.get(
            "/users/me/cards",
            params={"cursor": cursor},
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
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

        card_service.get_all_by_user_id.assert_not_awaited()


class TestGetMyTrainingSessions:
    async def test_returns_current_user_training_sessions(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_all_by_user_uuid.return_value = (
            [training_session],
            None,
            False,
        )

        response = await client.get("/users/me/training-sessions")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                    "deck_uuid": ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                    "status": "in_progress",
                    "requested_count": 10,
                    "actual_count": 3,
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
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
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
            ),
        ]

        training_session_service.get_all_by_user_uuid.return_value = (
            training_sessions,
            None,
            False,
        )

        response = await client.get("/users/me/training-sessions")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                    "deck_uuid": ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                    "status": "in_progress",
                    "requested_count": 10,
                    "actual_count": 3,
                    "correct_count": 2,
                    "wrong_count": 1,
                    "prompt_side": "front",
                    "answer_side": "back",
                    "started_at": "2026-08-15T16:00:00Z",
                    "finished_at": None,
                },
                {
                    "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                    "deck_uuid": ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                    "status": "completed",
                    "requested_count": 10,
                    "actual_count": 3,
                    "correct_count": 2,
                    "wrong_count": 1,
                    "prompt_side": "front",
                    "answer_side": "back",
                    "started_at": "2026-08-15T16:00:00Z",
                    "finished_at": None,
                },
            ],
            "next_cursor": None,
            "has_more": False,
        }

        assert response.json() == expected

        (
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
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
        training_session_service.get_all_by_user_uuid.return_value = (
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
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
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

        training_session_service.get_all_by_user_uuid.return_value = (
            [training_session],
            next_cursor,
            True,
        )

        response = await client.get("/users/me/training-sessions")

        assert response.status_code == status.HTTP_200_OK

        expected = {
            "items": [
                {
                    "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                    "deck_uuid": ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                    "status": "in_progress",
                    "requested_count": 10,
                    "actual_count": 3,
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
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
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
        training_session_service.get_all_by_user_uuid.return_value = (
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
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
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
        training_session_service.get_all_by_user_uuid.return_value = (
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
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
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
        training_session_service.get_all_by_user_uuid.return_value = (
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
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
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
            "message": "Validation error",
            "details": [expected_detail],
        }

        (training_session_service.get_all_by_user_uuid.assert_not_awaited())

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

        (training_session_service.get_all_by_user_uuid.assert_not_awaited())

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

        (training_session_service.get_all_by_user_uuid.assert_not_awaited())


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
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": ("12345678-1234-5678-1234-567812345678"),
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
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": ("12345678-1234-5678-1234-567812345678"),
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
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": ("12345678-1234-5678-1234-567812345678"),
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
            "message": "Validation error",
            "details": [expected_detail],
        }

        (user_deck_service.get_page_of_saved_decks_by_user_id.assert_not_awaited())


class TestGetPublicUser:
    async def test_returns_public_user(
        self,
        client: AsyncClient,
        user_service: AsyncMock,
    ):
        user = make_user()

        user_service.get_by_uuid.return_value = user

        response = await client.get(f"/users/{user.uuid}")

        expected = {
            "uuid": "12345678-1234-5678-1234-567812345678",
            "username": "test-user",
            "created_at": "2026-08-15T12:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        user_service.get_by_uuid.assert_awaited_once_with(
            user_uuid=user.uuid,
            for_update=False,
        )

    async def test_rejects_invalid_uuid(
        self,
        client: AsyncClient,
        user_service: AsyncMock,
    ):
        response = await client.get("/users/not-a-uuid")

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
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

        user_service.get_by_uuid.assert_not_awaited()


class TestCreateUser:
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

        user_service.create_user.return_value = (
            new_user,
            user_settings,
        )

        response = await client.post(
            "/users/create",
            json=payload,
        )

        expected = {
            "uuid": "12345678-1234-5678-1234-567812345678",
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
            username="new-user",
            email="new@example.com",
        )
        user_settings = make_user_settings()

        user_service.create_user.return_value = (
            new_user,
            user_settings,
        )

        response = await client.post(
            "/users/create",
            json=payload,
        )

        expected = {
            "uuid": "12345678-1234-5678-1234-567812345678",
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

        user_service.create_user.assert_awaited_once_with(
            CreateUserRequest(
                username="new-user",
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
        user_service.create_user.return_value = (
            new_user,
            user_settings,
        )

        response = await client.post(
            "/users/create",
            json=payload,
        )

        expected = {
            "uuid": "12345678-1234-5678-1234-567812345678",
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
                    "msg": "String should match pattern '^\\S+$'",
                    "input": "user name",
                    "ctx": {"pattern": r"^\S+$"},
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
            "uuid": "12345678-1234-5678-1234-567812345678",
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
            target_user_uuid=current_user.uuid,
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
            "uuid": "12345678-1234-5678-1234-567812345678",
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
            target_user_uuid=current_user.uuid,
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
                "renamed-user",
                "renamed@example.com",
                {
                    "username": "renamed-user",
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
            "uuid": "12345678-1234-5678-1234-567812345678",
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
            target_user_uuid=current_user.uuid,
            current_user_id=current_user.id,
            payload=UpdateUserRequest(**expected_service_payload),
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {"username": "ab"},
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
                {"username": "a" * 19},
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
                {"username": "user name"},
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["body", "username"],
                    "msg": "String should match pattern '^\\S+$'",
                    "input": "user name",
                    "ctx": {"pattern": r"^\S+$"},
                },
                id="username_contains_spaces",
            ),
            pytest.param(
                {"email": "not-an-email"},
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
        ],
    )
    async def test_rejects_invalid_payload(
        self,
        client: AsyncClient,
        payload,
        expected_detail,
        user_service: AsyncMock,
    ):
        response = await client.patch(
            "/users/me",
            json=payload,
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
        }

        user_service.update_user.assert_not_awaited()

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({}, id="empty_body"),
            pytest.param({"username": None}, id="username_null"),
            pytest.param({"email": None}, id="email_null"),
            pytest.param(
                {"username": None, "email": None},
                id="all_fields_null",
            ),
        ],
    )
    async def test_returns_422_when_update_body_has_no_values(
        self,
        client: AsyncClient,
        current_user,
        payload,
        user_service: AsyncMock,
    ):
        user_service.update_user.side_effect = RequestValueError(
            message="Update body is empty",
            failed_field="body",
        )

        response = await client.patch(
            "/users/me",
            json=payload,
        )

        expected = {
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

        user_service.update_user.assert_awaited_once_with(
            target_user_uuid=current_user.uuid,
            current_user_id=current_user.id,
            payload=UpdateUserRequest(**payload),
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                UserNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "User not found",
                id="user_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
                "Permission denied",
                id="permission_denied",
            ),
            pytest.param(
                UserAlreadyExistsError(),
                status.HTTP_409_CONFLICT,
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
        assert response.json() == {"message": expected_message}

        user_service.update_user.assert_awaited_once_with(
            target_user_uuid=current_user.uuid,
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
            target_user_uuid=current_user.uuid,
        )

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                UserNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "User not found",
                id="user_not_found",
            ),
            pytest.param(
                PermissionDeniedError(),
                status.HTTP_403_FORBIDDEN,
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
        expected_message,
        user_service: AsyncMock,
    ):
        user_service.delete_user.side_effect = service_error

        response = await client.delete("/users/me")

        assert response.status_code == expected_status
        assert response.json() == {"message": expected_message}
        assert response.headers.get_list("set-cookie") == []

        user_service.delete_user.assert_awaited_once_with(
            current_user_id=current_user.id,
            target_user_uuid=current_user.uuid,
        )


class TestGetPublicTrainingSessionsByUser:
    async def test_returns_completed_training_sessions(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        user = make_user()
        training_session = make_training_session(
            status=TrainingSessionStatus.COMPLETED,
            finished_at=datetime(2026, 8, 15, 17, 0, tzinfo=UTC),
        )
        training_session_service.get_all_by_user_uuid.return_value = (
            [training_session],
            "next-page-cursor",
            True,
        )

        response = await client.get(f"/users/{user.uuid}/training-sessions")

        expected = {
            "items": [
                {
                    "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                    "deck_uuid": ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                    "status": "completed",
                    "requested_count": 10,
                    "actual_count": 3,
                    "correct_count": 2,
                    "wrong_count": 1,
                    "prompt_side": "front",
                    "answer_side": "back",
                    "started_at": "2026-08-15T16:00:00Z",
                    "finished_at": "2026-08-15T17:00:00Z",
                }
            ],
            "next_cursor": "next-page-cursor",
            "has_more": True,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        (
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
                user_uuid=user.uuid,
                status=TrainingSessionStatus.COMPLETED,
                cursor=None,
                limit=20,
            )
        )

    async def test_returns_empty_page(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        user = make_user()
        training_session_service.get_all_by_user_uuid.return_value = (
            [],
            None,
            False,
        )

        response = await client.get(f"/users/{user.uuid}/training-sessions")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        (
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
                user_uuid=user.uuid,
                status=TrainingSessionStatus.COMPLETED,
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
        limit,
        cursor,
        training_session_service: AsyncMock,
    ):
        user = make_user()
        training_session_service.get_all_by_user_uuid.return_value = (
            [],
            None,
            False,
        )

        response = await client.get(
            f"/users/{user.uuid}/training-sessions",
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
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
                user_uuid=user.uuid,
                status=TrainingSessionStatus.COMPLETED,
                cursor=cursor,
                limit=limit,
            )
        )

    async def test_returns_404_when_user_not_found(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        user = make_user()
        training_session_service.get_all_by_user_uuid.side_effect = UserNotFoundError()

        response = await client.get(f"/users/{user.uuid}/training-sessions")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"message": "User not found"}

        (
            training_session_service.get_all_by_user_uuid.assert_awaited_once_with(
                user_uuid=user.uuid,
                status=TrainingSessionStatus.COMPLETED,
                cursor=None,
                limit=20,
            )
        )

    async def test_rejects_invalid_user_uuid(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        response = await client.get("/users/not-a-uuid/training-sessions")

        expected = {
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

        training_session_service.get_all_by_user_uuid.assert_not_awaited()

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
        user = make_user()

        response = await client.get(
            f"/users/{user.uuid}/training-sessions",
            params={"limit": limit},
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "message": "Validation error",
            "details": [expected_detail],
        }

        training_session_service.get_all_by_user_uuid.assert_not_awaited()

    async def test_rejects_too_long_cursor(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        user = make_user()
        cursor = "a" * 513

        response = await client.get(
            f"/users/{user.uuid}/training-sessions",
            params={"cursor": cursor},
        )

        expected = {
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

        training_session_service.get_all_by_user_uuid.assert_not_awaited()


class TestGetPublicDecksByUser:
    async def test_returns_public_decks(
        self,
        client: AsyncClient,
        deck,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_all_by_user_uuid.return_value = (
            [deck],
            "next-page-cursor",
            True,
        )

        response = await client.get(f"/users/{user.uuid}/decks")

        expected = {
            "items": [
                {
                    "uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "owner_uuid": ("12345678-1234-5678-1234-567812345678"),
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

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=user.uuid,
            search_query=None,
            cursor=None,
            limit=30,
            public_only=True,
            current_user_id=None,
        )

    async def test_returns_empty_page(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_all_by_user_uuid.return_value = (
            [],
            None,
            False,
        )

        response = await client.get(f"/users/{user.uuid}/decks")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "items": [],
            "next_cursor": None,
            "has_more": False,
        }

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=user.uuid,
            search_query=None,
            cursor=None,
            limit=30,
            public_only=True,
            current_user_id=None,
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
        raw_query,
        normalized_query,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_all_by_user_uuid.return_value = (
            [],
            None,
            False,
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

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=user.uuid,
            search_query=normalized_query,
            cursor=None,
            limit=30,
            public_only=True,
            current_user_id=None,
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
        limit,
        cursor,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_all_by_user_uuid.return_value = (
            [],
            None,
            False,
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

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=user.uuid,
            search_query=None,
            cursor=cursor,
            limit=limit,
            public_only=True,
            current_user_id=None,
        )

    async def test_returns_404_when_user_not_found(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        user = make_user()
        deck_service.get_all_by_user_uuid.side_effect = UserNotFoundError()

        response = await client.get(f"/users/{user.uuid}/decks")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"message": "User not found"}

        deck_service.get_all_by_user_uuid.assert_awaited_once_with(
            user_uuid=user.uuid,
            search_query=None,
            cursor=None,
            limit=30,
            public_only=True,
            current_user_id=None,
        )

    async def test_rejects_invalid_user_uuid(
        self,
        client: AsyncClient,
        deck_service: AsyncMock,
    ):
        response = await client.get("/users/not-a-uuid/decks")

        expected = {
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

        deck_service.get_all_by_user_uuid.assert_not_awaited()

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
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_all_by_user_uuid.assert_not_awaited()

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
            "message": "Validation error",
            "details": [expected_detail],
        }

        deck_service.get_all_by_user_uuid.assert_not_awaited()

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

        deck_service.get_all_by_user_uuid.assert_not_awaited()
