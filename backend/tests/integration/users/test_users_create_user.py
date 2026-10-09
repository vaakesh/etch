import asyncio
from datetime import datetime
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.auth.utils import verify_password
from app.users.models import User, UserSettings
from tests.integration.conftest import ClientFactory, solve_captcha
from tests.integration.users.conftest import (
    AuthClientFactory,
    UserFactory,
    UserPayloadFactory,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestUserCreate:
    @pytest.mark.parametrize(
        ("username", "email", "expected_username"),
        [
            pytest.param("alice", "alice@example.com", "alice", id="normalized"),
            pytest.param(
                "  AlIcE  ",
                "  ALICE@EXAMPLE.COM  ",
                "AlIcE",
                id="normalizes_fields_and_preserves_username_case",
            ),
        ],
    )
    async def test_returns_created_user_and_persists_user_with_settings(
        self,
        client_factory: ClientFactory,
        user_payload_factory: UserPayloadFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        username: str,
        email: str,
        expected_username: str,
    ):
        client = await client_factory()
        payload = user_payload_factory(
            username=username,
            email=email,
            password="Test-password-123",
        )

        response = await client.post(
            "/users/create",
            json=payload,
            headers=await solve_captcha(client),
        )

        assert response.status_code == 201
        data = response.json()

        async with async_session_maker() as session:
            result = await session.execute(
                select(User)
                .where(User.email == "alice@example.com")
                .options(selectinload(User.settings))
            )
            user = result.scalar_one_or_none()

            assert user is not None
            assert user.username == expected_username
            assert user.email == "alice@example.com"
            assert user.settings is not None
            assert user.settings.user_id == user.id
            assert user.settings.locale == "ru-RU"
            assert user.settings.theme == "system"
            assert user.settings.show_previews_for_long is True

            assert user.hashed_password != payload["password"]
            assert verify_password(payload["password"], user.hashed_password)

            response_uuid = data.pop("uuid")
            assert UUID(response_uuid).version == 7
            assert response_uuid == str(user.uuid)

            created_at = datetime.fromisoformat(data.pop("created_at"))
            updated_at = datetime.fromisoformat(data.pop("updated_at"))
            assert created_at == user.created_at
            assert updated_at == user.updated_at
            assert updated_at >= created_at

        assert data == {
            "username": expected_username,
            "email": "alice@example.com",
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }

    @pytest.mark.parametrize(
        ("username", "email", "expected_code", "expected_message"),
        [
            pytest.param(
                "Alice", "bob@example.com",
                "USERNAME_ALREADY_EXISTS", "Username is already in use",
                id="username_taken",
            ),
            pytest.param(
                "alice", "bob@example.com",
                "USERNAME_ALREADY_EXISTS", "Username is already in use",
                id="username_case_insensitive",
            ),
            pytest.param(
                "bob", "alice@example.com",
                "EMAIL_ALREADY_EXISTS", "Email is already in use",
                id="email_taken",
            ),
            pytest.param(
                "bob",
                "  ALICE@EXAMPLE.COM  ",
                "EMAIL_ALREADY_EXISTS",
                "Email is already in use",
                id="email_taken_after_normalization",
            ),
        ],
    )
    async def test_returns_409_and_preserves_database_when_identity_is_taken(
        self,
        client: AsyncClient,
        user_factory: UserFactory,
        user_payload_factory: UserPayloadFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        username: str,
        email: str,
        expected_code: str,
        expected_message: str,
    ):
        await user_factory(username="Alice", email="alice@example.com")
        payload = user_payload_factory(
            username=username,
            email=email,
            password="Different-password-456",
        )

        async with async_session_maker() as session:
            users_before = (
                await session.execute(select(User.__table__))
            ).mappings().all()
            settings_before = (
                await session.execute(select(UserSettings.__table__))
            ).mappings().all()
        assert len(users_before) == 1
        assert len(settings_before) == 1

        response = await client.post(
            "/users/create",
            json=payload,
            headers=await solve_captcha(client),
        )

        assert response.status_code == 409
        assert response.json() == {
            "code": expected_code,
            "message": expected_message,
        }
        async with async_session_maker() as session:
            users_after = (
                await session.execute(select(User.__table__))
            ).mappings().all()
            settings_after = (
                await session.execute(select(UserSettings.__table__))
            ).mappings().all()

        assert users_after == users_before
        assert settings_after == settings_before

    async def test_returns_422_without_creating_user_when_email_is_invalid(
        self,
        client: AsyncClient,
        user_payload_factory: UserPayloadFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        payload = user_payload_factory(email="not-an-email")

        response = await client.post(
            "/users/create",
            json=payload,
            headers=await solve_captcha(client),
        )

        assert response.status_code == 422
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "value_error",
                    "loc": ["body", "email"],
                    "msg": (
                        "value is not a valid email address: An email "
                        "address must have an @-sign."
                    ),
                    "input": "not-an-email",
                    "ctx": {"reason": "An email address must have an @-sign."},
                }
            ],
        }
        async with async_session_maker() as session:
            user_ids = (await session.scalars(select(User.id))).all()
            settings_user_ids = (
                await session.scalars(select(UserSettings.user_id))
            ).all()

        assert user_ids == []
        assert settings_user_ids == []

    @pytest.mark.parametrize(
        ("second_username", "second_email", "expected_code", "expected_message"),
        [
            pytest.param(
                "alice", "bob@example.com",
                "USERNAME_ALREADY_EXISTS", "Username is already in use",
                id="same_username",
            ),
            pytest.param(
                "bob", "alice@example.com",
                "EMAIL_ALREADY_EXISTS", "Email is already in use",
                id="same_email",
            ),
        ],
    )
    async def test_creates_only_one_user_when_concurrent_requests_conflict(
        self,
        client_factory: ClientFactory,
        user_payload_factory: UserPayloadFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        second_username: str,
        second_email: str,
        expected_code: str,
        expected_message: str,
    ):
        first_client = await client_factory()
        second_client = await client_factory()
        first_payload = user_payload_factory(
            username="alice",
            email="alice@example.com",
            password="First-password-123",
        )
        second_payload = user_payload_factory(
            username=second_username,
            email=second_email,
            password="Second-password-456",
        )

        first_captcha = await solve_captcha(first_client)
        second_captcha = await solve_captcha(second_client)

        # Оба запроса запускаются без ожидания ответа первого.
        # TaskGroup дожидается завершения задач и при исключении в одной из них.
        async with asyncio.TaskGroup() as group:
            first_request = group.create_task(
                first_client.post(
                    "/users/create",
                    json=first_payload,
                    headers=first_captcha,
                )
            )
            second_request = group.create_task(
                second_client.post(
                    "/users/create",
                    json=second_payload,
                    headers=second_captcha,
                )
            )

        # Победитель не предопределён: связываем каждый ответ с его payload.
        (success, winning_payload), (conflict, _) = sorted(
            [
                (first_request.result(), first_payload),
                (second_request.result(), second_payload),
            ],
            key=lambda item: item[0].status_code,
        )
        assert success.status_code == 201
        assert conflict.status_code == 409
        assert conflict.json() == {
            "code": expected_code,
            "message": expected_message,
        }

        async with async_session_maker() as session:
            # one() проверяет, что в каждой таблице ровно одна запись.
            user = (await session.scalars(select(User))).one()
            settings = (await session.scalars(select(UserSettings))).one()
            assert user.username == winning_payload["username"]
            assert user.email == winning_payload["email"]
            assert verify_password(winning_payload["password"], user.hashed_password)
            assert settings.user_id == user.id
            assert settings.locale == "ru-RU"
            assert settings.theme == "system"
            assert settings.show_previews_for_long is True

            data = success.json()
            response_uuid = data.pop("uuid")
            assert UUID(response_uuid).version == 7
            assert response_uuid == str(user.uuid)
            created_at = datetime.fromisoformat(data.pop("created_at"))
            updated_at = datetime.fromisoformat(data.pop("updated_at"))
            assert created_at == user.created_at
            assert updated_at == user.updated_at
            assert updated_at >= created_at

        assert data == {
            "username": winning_payload["username"],
            "email": winning_payload["email"],
            "settings": {
                "locale": "ru-RU",
                "theme": "system",
                "show_previews_for_long": True,
            },
        }


class TestUserClientIsolation:
    async def test_each_client_sees_its_own_user(
        self, 
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        bob = await user_factory(username="bob", email="bob@example.com")
        alice_client = await auth_client_factory(alice)
        bob_client = await auth_client_factory(bob)

        alice_response = await alice_client.get("/users/me")
        bob_response = await bob_client.get("/users/me")

        assert alice_response.status_code == 200
        assert alice_response.json() == {
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
        assert bob_response.status_code == 200
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
