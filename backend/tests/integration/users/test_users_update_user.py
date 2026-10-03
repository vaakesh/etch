import logging
from datetime import datetime
from uuid import UUID

import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.users.models import User, UserSettings
from tests.integration.conftest import ClientFactory
from tests.integration.users.conftest import AuthClientFactory, UserFactory

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestUserUpdate:
    async def test_updates_all_fields_and_returns_persisted_values(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)
        update_payload = {
            "username": "Bob",
            "email": "bob@example.com",
        }

        response = await alice_client.patch(
            url="/users/me",
            json=update_payload,
        )
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data == {
            "uuid": alice.uuid,
            "username": "Bob",
            "email": "bob@example.com",
            "created_at": alice.created_at,
            "updated_at": data["updated_at"],
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            settings = (await session.scalars(select(UserSettings))).one()
            assert user.username == "Bob"
            assert user.email == "bob@example.com"
            assert user.uuid == UUID(alice.uuid)
            assert user.created_at == datetime.fromisoformat(alice.created_at)
            assert user.updated_at == datetime.fromisoformat(data["updated_at"])
            assert settings.user_id == user.id
            assert settings.locale == "ru-RU"
            assert settings.theme == "system"
            assert settings.show_previews_for_long is True

    @pytest.mark.parametrize(
        ("update_payload", "expected"),
        [
            pytest.param(
                {"username": "bob"},
                {"username": "bob", "email": "alice@example.com"},
                id="updates_only_username",
            ),
            pytest.param(
                {"email": "bob@example.com"},
                {"username": "alice", "email": "bob@example.com"},
                id="updates_only_email",
            ),
        ]
    )
    async def test_updates_only_provided_fields(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        update_payload: dict,
        expected: dict,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch(
            url="/users/me",
            json=update_payload,
        )
        data = response.json()

        assert response.status_code == status.HTTP_200_OK
        assert data == {
            "uuid": alice.uuid,
            "username": expected["username"],
            "email": expected["email"],
            "created_at": alice.created_at,
            "updated_at": data["updated_at"],
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            assert user.username == expected["username"]
            assert user.email == expected["email"]
            assert user.updated_at == datetime.fromisoformat(data["updated_at"])

    @pytest.mark.parametrize(
        "update_payload",
        [
            pytest.param(
                {},
                id="empty_payload",
            ),
            pytest.param(
                {"unknown": "value"},
                id="unknown_field_only",
            ),
        ]
    )
    async def test_rejects_empty_update_without_changing_user(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        update_payload: dict,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch(
            url="/users/me",
            json=update_payload,
        )
        data = response.json()

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert data == {
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

        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            user_settings = (await session.scalars(select(UserSettings))).one()
            assert user.uuid == UUID(alice.uuid)
            assert user.username == alice.username
            assert user.email == alice.email
            assert user_settings.locale == alice.settings.locale
            assert user_settings.theme == alice.settings.theme
            assert user_settings.show_previews_for_long is alice.settings.show_previews_for_long

    @pytest.mark.parametrize(
        ("update_payload", "expected_code", "expected_message"),
        [
            pytest.param(
                {"username": "bob", "email": "alice@example.com"},
                "EMAIL_ALREADY_EXISTS",
                "Email is already in use",
                id="email_taken_with_username_change",
            ),
            pytest.param(
                {"username": "alice", "email": "bob@example.com"},
                "USERNAME_ALREADY_EXISTS",
                "Username is already in use",
                id="username_taken_with_email_change",
            ),
            pytest.param(
                {"email": "ALICE@example.com"},
                "EMAIL_ALREADY_EXISTS",
                "Email is already in use",
                id="email_case_insensitive",
            ),
            pytest.param(
                {"username": "ALICE"},
                "USERNAME_ALREADY_EXISTS",
                "Username is already in use",
                id="username_case_insensitive",
            ),
        ]
    )
    async def test_returns_409_when_identity_is_taken(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        update_payload: dict,
        expected_code: str,
        expected_message: str,
    ):
        alice = await user_factory(username="Alice", email="alice@example.com")
        kevin = await user_factory(username="Kevin", email="kevin@example.com")
        kevin_client = await auth_client_factory(kevin)

        response = await kevin_client.patch(
            url="/users/me",
            json=update_payload,
        )
        data = response.json()

        assert response.status_code == status.HTTP_409_CONFLICT
        assert data == {
            "code": expected_code,
            "message": expected_message,
        }

        async with async_session_maker() as session:
            kevin_user = (
                await session.execute(
                    select(User)
                    .where(User.uuid == kevin.uuid)
                    .options(selectinload(User.settings))
                )
            ).scalar_one()
            assert kevin_user.username == kevin.username
            assert kevin_user.email == kevin.email
            assert kevin_user.settings.locale == kevin.settings.locale
            assert kevin_user.settings.theme == kevin.settings.theme
            assert (
                kevin_user.settings.show_previews_for_long
                is kevin.settings.show_previews_for_long
            )

    async def test_normalizes_username_and_email_together(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch(
            "/users/me",
            json={
                "username": "  ReNaMeD-User  ",
                "email": "  RENAMED@EXAMPLE.COM  ",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == {
            "uuid": alice.uuid,
            "username": "ReNaMeD-User",
            "email": "renamed@example.com",
            "created_at": alice.created_at,
            "updated_at": data["updated_at"],
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            assert user.username == "ReNaMeD-User"
            assert user.email == "renamed@example.com"
            assert user.updated_at == datetime.fromisoformat(data["updated_at"])

    @pytest.mark.parametrize("username", ["abc", "a" * 18])
    async def test_accepts_username_length_boundaries(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        username: str,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch(
            "/users/me", json={"username": username}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == {
            "uuid": alice.uuid,
            "username": username,
            "email": "alice@example.com",
            "created_at": alice.created_at,
            "updated_at": data["updated_at"],
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            assert user.username == username

    async def test_allows_updating_own_identity_without_uniqueness_conflict(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="Alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch(
            "/users/me",
            json={"username": "ALICE", "email": "ALICE@EXAMPLE.COM"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == {
            "uuid": alice.uuid,
            "username": "ALICE",
            "email": "alice@example.com",
            "created_at": alice.created_at,
            "updated_at": data["updated_at"],
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            assert user.username == "ALICE"
            assert user.email == "alice@example.com"

    @pytest.mark.parametrize("field", ["username", "email"])
    async def test_rejects_explicit_null_without_changing_user(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        field: str,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch("/users/me", json={field: None})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "value_error",
                    "loc": ["body", field],
                    "msg": "Field must not be null",
                    "input": None,
                }
            ],
        }
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            assert user.username == "alice"
            assert user.email == "alice@example.com"

    @pytest.mark.parametrize(
        ("invalid_field", "invalid_value", "expected_detail"),
        [
            pytest.param(
                "username",
                "ab",
                {
                    "type": "string_too_short",
                    "loc": ["body", "username", "constrained-str"],
                    "msg": "String should have at least 3 characters",
                    "input": "ab",
                    "ctx": {"min_length": 3},
                },
                id="username_too_short",
            ),
            pytest.param(
                "username",
                "a" * 19,
                {
                    "type": "string_too_long",
                    "loc": ["body", "username", "constrained-str"],
                    "msg": "String should have at most 18 characters",
                    "input": "a" * 19,
                    "ctx": {"max_length": 18},
                },
                id="username_too_long",
            ),
            pytest.param(
                "username",
                "user name",
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["body", "username", "constrained-str"],
                    "msg": "String should match pattern '^[A-Za-z0-9_-]+$'",
                    "input": "user name",
                    "ctx": {"pattern": r"^[A-Za-z0-9_-]+$"},
                },
                id="username_contains_spaces",
            ),
        ],
    )
    async def test_rejects_invalid_field_without_partial_write(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        invalid_field: str,
        invalid_value: str,
        expected_detail: dict,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)
        payload = {
            "username": "renamed",
            "email": "renamed@example.com",
            invalid_field: invalid_value,
        }

        response = await alice_client.patch("/users/me", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                expected_detail,
                {
                    "type": "none_required",
                    "loc": ["body", invalid_field, "none"],
                    "msg": "Input should be None",
                    "input": invalid_value,
                },
            ],
        }
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            assert user.username == "alice"
            assert user.email == "alice@example.com"

    async def test_rejects_invalid_email_without_updating_username(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch(
            "/users/me",
            json={"username": "renamed", "email": "not-an-email"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"
        assert data["message"] == "Validation error"
        assert len(data["details"]) == 2
        email_error = data["details"][0]
        assert email_error["loc"][:2] == ["body", "email"]
        assert len(email_error["loc"]) == 3
        assert {key: value for key, value in email_error.items() if key != "loc"} == {
            "type": "value_error",
            "msg": (
                "value is not a valid email address: An email "
                "address must have an @-sign."
            ),
            "input": "not-an-email",
            "ctx": {"reason": "An email address must have an @-sign."},
        }
        assert data["details"][1] == {
            "type": "none_required",
            "loc": ["body", "email", "none"],
            "msg": "Input should be None",
            "input": "not-an-email",
        }
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            assert user.username == "alice"
            assert user.email == "alice@example.com"

    async def test_rejects_unauthenticated_update_without_changing_user(
        self,
        user_factory: UserFactory,
        client_factory: ClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        await user_factory(username="alice", email="alice@example.com")
        guest_client = await client_factory()

        response = await guest_client.patch(
            "/users/me", json={"username": "renamed"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {
            "code": "ACCESS_TOKEN_NOT_FOUND",
            "message": "Not authorized",
        }
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            assert user.username == "alice"

    async def test_other_session_sees_updated_identity(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        first_client = await auth_client_factory(alice)
        second_client = await auth_client_factory(alice)
        before = await second_client.get("/users/me")
        assert before.status_code == status.HTTP_200_OK
        assert before.json() == {
            "uuid": alice.uuid,
            "username": "alice",
            "email": "alice@example.com",
            "created_at": alice.created_at,
            "updated_at": alice.updated_at,
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

        update = await first_client.patch(
            "/users/me",
            json={"username": "renamed", "email": "renamed@example.com"},
        )
        after = await second_client.get("/users/me")

        assert update.status_code == status.HTTP_200_OK
        assert after.status_code == status.HTTP_200_OK
        assert after.json() == update.json()
        assert after.json()["username"] == "renamed"
        assert after.json()["email"] == "renamed@example.com"

    async def test_update_does_not_change_another_user(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        bob = await user_factory(username="bob", email="bob@example.com")
        alice_client = await auth_client_factory(alice)
        bob_client = await auth_client_factory(bob)

        update = await alice_client.patch(
            "/users/me", json={"username": "renamed"}
        )
        bob_response = await bob_client.get("/users/me")

        assert update.status_code == status.HTTP_200_OK
        assert bob_response.status_code == status.HTTP_200_OK
        assert bob_response.json() == {
            "uuid": bob.uuid,
            "username": "bob",
            "email": "bob@example.com",
            "created_at": bob.created_at,
            "updated_at": bob.updated_at,
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }
        async with async_session_maker() as session:
            users = (await session.scalars(select(User))).all()
            assert len(users) == 2
            assert {user.username for user in users} == {"renamed", "bob"}
