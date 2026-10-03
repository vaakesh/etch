import logging
from http.cookies import SimpleCookie
from uuid import UUID

import pytest
from fastapi import status
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.models import UserSession
from app.cards.models import Card
from app.decks.models import Deck, DeckCard, UserDeck
from app.users.models import User, UserSettings
from tests.integration.conftest import ClientFactory
from tests.integration.users.conftest import AuthClientFactory, UserFactory

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestUserDelete:
    async def test_deletes_user_settings_and_session_and_clears_cookies(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.delete(
            url="/users/me",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
        cookies = SimpleCookie()
        for header in response.headers.get_list("set-cookie"):
            cookies.load(header)
        assert set(cookies) == {"access_token", "refresh_token"}
        assert all(cookie.value == "" and cookie["max-age"] == "0" for cookie in cookies.values())

        async with async_session_maker() as session:
            stmt = select(
                exists(select(User.id)).label("has_users"),
                exists(select(UserSettings.user_id)).label("has_user_settings"),
                exists(select(UserSession.id)).label("has_user_sessions"),
            )
            has_users, has_user_settings, has_user_sessions = (await session.execute(stmt)).one()
            assert has_users is False
            assert has_user_settings is False
            assert has_user_sessions is False

    async def test_rejects_unauthenticated_delete_without_changing_user(
        self,
        client_factory: ClientFactory,
        user_factory: UserFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        guest_client = await client_factory()

        response = await guest_client.delete("/users/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {
            "code": "ACCESS_TOKEN_NOT_FOUND",
            "message": "Not authorized",
        }
        assert response.headers.get_list("set-cookie") == []
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            settings = (await session.scalars(select(UserSettings))).one()
            assert user.uuid == UUID(alice.uuid)
            assert user.username == "alice"
            assert user.email == "alice@example.com"
            assert settings.user_id == user.id

    async def test_preserves_other_user_and_session(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        bob = await user_factory(username="bob", email="bob@example.com")
        alice_client = await auth_client_factory(alice)
        bob_client = await auth_client_factory(bob)

        response = await alice_client.delete("/users/me")
        bob_response = await bob_client.get("/users/me")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""
        assert bob_response.status_code == status.HTTP_200_OK
        assert bob_response.json() == {
            "uuid": bob.uuid,
            "username": bob.username,
            "email": bob.email,
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
            settings = (await session.scalars(select(UserSettings))).all()
            user_sessions = (await session.scalars(select(UserSession))).all()
            assert [user.uuid for user in users] == [UUID(bob.uuid)]
            assert [item.user_id for item in settings] == [users[0].id]
            assert [item.user_id for item in user_sessions] == [users[0].id]

    async def test_invalidates_another_session_of_deleted_user(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        first_client = await auth_client_factory(alice)
        second_client = await auth_client_factory(alice)
        before = await second_client.get("/users/me")
        assert before.status_code == status.HTTP_200_OK

        response = await first_client.delete("/users/me")
        after = await second_client.get("/users/me")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert after.status_code == status.HTTP_404_NOT_FOUND
        assert after.json() == {
            "code": "USER_NOT_FOUND",
            "message": f"User with uuid={alice.uuid} not found",
        }
        async with async_session_maker() as session:
            assert (await session.scalars(select(UserSession.id))).all() == []
