from datetime import UTC, datetime
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from app.auth.deps import get_current_user
from app.auth.errors import (
    AccessTokenNotFoundError,
    InvalidLoginCredentials,
    InvalidRefreshTokenError,
)
from app.auth.schemas import AccessTokenResponse
from app.users.errors import UserNotFoundError
from tests.unit.factories import make_token_pair, make_user_session


class TestLoginForBearerToken:
    async def test_returns_bearer_access_token(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        auth_service.login_by_bearer_token_without_refresh.return_value = (
            AccessTokenResponse(access_token="bearer-access-token")
        )

        response = await client.post(
            "/auth/token",
            data={"username": "test-user", "password": "password123"},
        )

        expected = {
            "access_token": "bearer-access-token",
            "token_type": "Bearer",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        (
            auth_service.login_by_bearer_token_without_refresh.assert_awaited_once_with(
                username="test-user",
                password="password123",
            )
        )

    async def test_returns_404_for_invalid_credentials(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        auth_service.login_by_bearer_token_without_refresh.side_effect = (
            InvalidLoginCredentials()
        )

        response = await client.post(
            "/auth/token",
            data={"username": "test-user", "password": "wrong-password"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["message"] == "Invalid username or password"
        (
            auth_service.login_by_bearer_token_without_refresh.assert_awaited_once_with(
                username="test-user",
                password="wrong-password",
            )
        )

    @pytest.mark.parametrize(
        ("form_data", "field"),
        [
            pytest.param(
                {"password": "password123"},
                "username",
                id="username_missing",
            ),
            pytest.param(
                {"username": "test-user"},
                "password",
                id="password_missing",
            ),
        ],
    )
    async def test_rejects_missing_form_field(
        self,
        client: AsyncClient,
        form_data,
        field,
        auth_service: AsyncMock,
    ):
        response = await client.post("/auth/token", data=form_data)

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "missing",
                    "loc": ["body", field],
                    "msg": "Field required",
                    "input": None,
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected
        (auth_service.login_by_bearer_token_without_refresh.assert_not_awaited())


class TestLogin:
    async def test_logs_in_and_sets_token_cookies(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        auth_service.login.return_value = make_token_pair()
        payload = {"username": "test-user", "password": "password123"}

        response = await client.post("/auth/login", json=payload)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        set_cookie_headers = response.headers.get_list("set-cookie")
        cookies = SimpleCookie()
        cookies.load(set_cookie_headers[0])
        cookies.load(set_cookie_headers[1])

        assert len(set_cookie_headers) == 2
        assert set(cookies) == {"access_token", "refresh_token"}

        access_token = cookies["access_token"]
        assert access_token.value == "test-access-token"
        assert access_token["max-age"] == "3000"
        assert access_token["path"] == "/"
        assert access_token["secure"] is True
        assert access_token["httponly"] is True
        assert access_token["samesite"] == "lax"

        refresh_token = cookies["refresh_token"]
        assert refresh_token.value == "test-refresh-token"
        assert refresh_token["max-age"] == "604800"
        assert refresh_token["path"] == "/"
        assert refresh_token["secure"] is True
        assert refresh_token["httponly"] is True
        assert refresh_token["samesite"] == "lax"

        auth_service.login.assert_awaited_once_with(
            username="test-user",
            password="password123",
        )

    async def test_normalizes_username_without_changing_password(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        auth_service.login.return_value = make_token_pair()
        payload = {
            "username": "  TeSt-UsEr  ",
            "password": "Password123",
        }

        response = await client.post("/auth/login", json=payload)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        cookies = SimpleCookie()
        for header in response.headers.get_list("set-cookie"):
            cookies.load(header)
        assert cookies["access_token"].value == "test-access-token"
        assert cookies["refresh_token"].value == "test-refresh-token"

        auth_service.login.assert_awaited_once_with(
            username="test-user",
            password="Password123",
        )

    @pytest.mark.parametrize(
        ("username", "password"),
        [
            pytest.param("abc", "a" * 8, id="minimum_lengths"),
            pytest.param("a" * 18, "a" * 128, id="maximum_lengths"),
        ],
    )
    async def test_accepts_boundary_credentials(
        self,
        client: AsyncClient,
        username,
        password,
        auth_service: AsyncMock,
    ):
        auth_service.login.return_value = make_token_pair()

        response = await client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        cookies = SimpleCookie()
        for header in response.headers.get_list("set-cookie"):
            cookies.load(header)
        assert cookies["access_token"].value == "test-access-token"
        assert cookies["refresh_token"].value == "test-refresh-token"

        auth_service.login.assert_awaited_once_with(
            username=username,
            password=password,
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {"username": "ab", "password": "password123"},
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
                {"username": "a" * 19, "password": "password123"},
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
                {"username": "test user", "password": "password123"},
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["body", "username"],
                    "msg": "String should match pattern '^\\S+$'",
                    "input": "test user",
                    "ctx": {"pattern": r"^\S+$"},
                },
                id="username_contains_spaces",
            ),
            pytest.param(
                {"username": "test-user", "password": "short"},
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
                {"username": "test-user", "password": "a" * 129},
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
                    "username": "test-user",
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
    async def test_rejects_invalid_credentials_schema(
        self,
        client: AsyncClient,
        payload,
        expected_detail,
        auth_service: AsyncMock,
    ):
        response = await client.post("/auth/login", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }
        assert response.headers.get_list("set-cookie") == []
        auth_service.login.assert_not_awaited()

    @pytest.mark.parametrize(
        ("payload", "expected_details"),
        [
            pytest.param(
                {"password": "password123"},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "username"],
                        "msg": "Field required",
                        "input": {"password": "password123"},
                    }
                ],
                id="username_missing",
            ),
            pytest.param(
                {"username": "test-user"},
                [
                    {
                        "type": "missing",
                        "loc": ["body", "password"],
                        "msg": "Field required",
                        "input": {"username": "test-user"},
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
                        "loc": ["body", "password"],
                        "msg": "Field required",
                        "input": {},
                    },
                ],
                id="both_fields_missing",
            ),
        ],
    )
    async def test_rejects_missing_credentials(
        self,
        client: AsyncClient,
        payload,
        expected_details,
        auth_service: AsyncMock,
    ):
        response = await client.post("/auth/login", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": expected_details,
        }
        assert response.headers.get_list("set-cookie") == []
        auth_service.login.assert_not_awaited()

    async def test_returns_404_without_cookies_for_invalid_credentials(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        payload = {"username": "test-user", "password": "wrong-password"}
        auth_service.login.side_effect = InvalidLoginCredentials()

        response = await client.post("/auth/login", json=payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["message"] == "Invalid username or password"
        assert response.headers.get_list("set-cookie") == []
        auth_service.login.assert_awaited_once_with(
            username="test-user",
            password="wrong-password",
        )


class TestLogout:
    async def test_logs_out_refresh_session_and_clears_cookies(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        client.cookies.set("refresh_token", "active-refresh-token")

        response = await client.post("/auth/logout")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None

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

        auth_service.logout.assert_awaited_once_with("active-refresh-token")

    async def test_logs_out_without_refresh_cookie(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        response = await client.post("/auth/logout")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() is None

        set_cookie_headers = response.headers.get_list("set-cookie")
        cookies = SimpleCookie()
        cookies.load(set_cookie_headers[0])
        cookies.load(set_cookie_headers[1])

        assert len(set_cookie_headers) == 2
        assert set(cookies) == {"access_token", "refresh_token"}
        assert cookies["access_token"].value == ""
        assert cookies["access_token"]["max-age"] == "0"
        assert cookies["refresh_token"].value == ""
        assert cookies["refresh_token"]["max-age"] == "0"
        auth_service.logout.assert_awaited_once_with(None)


class TestRefresh:
    async def test_refreshes_tokens_and_sets_new_cookies(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        auth_service.refresh.return_value = make_token_pair(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
        )

        client.cookies.set("refresh_token", "old-refresh-token")

        response = await client.post("/auth/refresh")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        set_cookie_headers = response.headers.get_list("set-cookie")
        cookies = SimpleCookie()
        cookies.load(set_cookie_headers[0])
        cookies.load(set_cookie_headers[1])

        assert len(set_cookie_headers) == 2
        assert set(cookies) == {"access_token", "refresh_token"}

        access_token = cookies["access_token"]
        assert access_token.value == "new-access-token"
        assert access_token["max-age"] == "3000"
        assert access_token["path"] == "/"
        assert access_token["secure"] is True
        assert access_token["httponly"] is True
        assert access_token["samesite"] == "lax"

        refresh_token = cookies["refresh_token"]
        assert refresh_token.value == "new-refresh-token"
        assert refresh_token["max-age"] == "604800"
        assert refresh_token["path"] == "/"
        assert refresh_token["secure"] is True
        assert refresh_token["httponly"] is True
        assert refresh_token["samesite"] == "lax"
        auth_service.refresh.assert_awaited_once_with("old-refresh-token")

    async def test_returns_401_when_refresh_cookie_missing(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        response = await client.post("/auth/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["message"] == "Refresh token not found"
        assert response.headers.get_list("set-cookie") == []
        auth_service.refresh.assert_not_awaited()

    async def test_returns_401_and_clears_cookies_for_invalid_refresh_token(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        auth_service.refresh.side_effect = InvalidRefreshTokenError()

        client.cookies.set("refresh_token", "invalid-refresh-token")

        response = await client.post("/auth/refresh")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["message"] == "Invalid refresh token"

        set_cookie_headers = response.headers.get_list("set-cookie")
        cookies = SimpleCookie()
        cookies.load(set_cookie_headers[0])
        cookies.load(set_cookie_headers[1])

        assert len(set_cookie_headers) == 2
        assert set(cookies) == {"access_token", "refresh_token"}
        assert cookies["access_token"].value == ""
        assert cookies["access_token"]["max-age"] == "0"
        assert cookies["refresh_token"].value == ""
        assert cookies["refresh_token"]["max-age"] == "0"
        auth_service.refresh.assert_awaited_once_with("invalid-refresh-token")

    async def test_returns_404_without_cookies_when_user_not_found(
        self,
        client: AsyncClient,
        auth_service: AsyncMock,
    ):
        auth_service.refresh.side_effect = UserNotFoundError()

        client.cookies.set("refresh_token", "active-refresh-token")

        response = await client.post("/auth/refresh")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["message"] == "User not found"
        assert response.headers.get_list("set-cookie") == []
        auth_service.refresh.assert_awaited_once_with("active-refresh-token")


class TestChangePassword:
    async def test_returns_401_when_user_is_not_authenticated(
        self,
        app: FastAPI,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        auth_service: AsyncMock,
    ):
        async def reject_unauthenticated_user():
            raise AccessTokenNotFoundError()

        monkeypatch.setitem(
            app.dependency_overrides,
            get_current_user,
            reject_unauthenticated_user,
        )
        payload = {
            "current_password": "old-password",
            "new_password": "new-password",
        }

        response = await client.put("/auth/password", json=payload)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {
            "code": "ACCESS_TOKEN_NOT_FOUND",
            "message": "Not authorized",
        }
        assert response.headers.get_list("set-cookie") == []
        auth_service.change_password.assert_not_awaited()

    async def test_returns_429_when_password_change_limit_is_exceeded(
        self,
        client: AsyncClient,
        current_user,
        redis_rate_limiter: AsyncMock,
        auth_service: AsyncMock,
    ):
        redis_rate_limiter.check.return_value = False
        payload = {
            "current_password": "old-password",
            "new_password": "new-password",
        }

        response = await client.put("/auth/password", json=payload)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert response.json() == {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
        }
        assert response.headers.get_list("set-cookie") == []
        redis_rate_limiter.check.assert_awaited_once_with(
            redis_key=f"rate_limit:user:{current_user.id}:users:password-change",
            requests=10,
            window_seconds=3600,
        )
        auth_service.change_password.assert_not_awaited()

    async def test_returns_404_without_clearing_cookies_when_current_password_is_wrong(
        self,
        client: AsyncClient,
        current_user,
        auth_service: AsyncMock,
    ):
        auth_service.change_password.side_effect = InvalidLoginCredentials()
        payload = {
            "current_password": "wrong-password",
            "new_password": "new-password",
        }

        response = await client.put("/auth/password", json=payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            "code": "INVALID_LOGIN_CREDENTIALS",
            "message": "Invalid username or password",
        }
        assert response.headers.get_list("set-cookie") == []
        auth_service.change_password.assert_awaited_once_with(
            user_id=current_user.id,
            current_password="wrong-password",
            new_password="new-password",
        )

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
            "/auth/password",
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
            "/auth/password",
            json=payload,
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
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
            "/auth/password",
            json=payload,
        )

        assert response.status_code == (status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": expected_details,
        }

        auth_service.change_password.assert_not_awaited()


class TestGetSessions:
    async def test_returns_user_sessions(
        self,
        client: AsyncClient,
        current_user,
        auth_service: AsyncMock,
    ):
        first_session = make_user_session()
        second_session = make_user_session(
            uuid=UUID("11111111-1111-1111-1111-111111111111"),
            user_agent=None,
            ip=None,
            revoked_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
            replaced_by_session_id=601,
        )
        auth_service.get_all_user_sessions.return_value = [
            first_session,
            second_session,
        ]

        response = await client.get("/auth/sessions")

        expected = [
            {
                "user_agent": "pytest",
                "ip": "127.0.0.1",
                "revoked_at": None,
            },
            {
                "user_agent": None,
                "ip": None,
                "revoked_at": "2026-08-16T12:00:00Z",
            },
        ]

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        auth_service.get_all_user_sessions.assert_awaited_once_with(current_user.id)

    async def test_returns_empty_session_list(
        self,
        client: AsyncClient,
        current_user,
        auth_service: AsyncMock,
    ):
        auth_service.get_all_user_sessions.return_value = []

        response = await client.get("/auth/sessions")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        auth_service.get_all_user_sessions.assert_awaited_once_with(current_user.id)
