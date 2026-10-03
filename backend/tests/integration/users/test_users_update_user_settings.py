import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.users.models import UserSettings
from tests.integration.conftest import ClientFactory
from tests.integration.users.conftest import AuthClientFactory, UserFactory


pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestUpdateUserSettings:
    async def test_updates_all_settings_and_returns_persisted_values(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)
        update_payload = {
            "locale": "en-US",
            "theme": "dark",
            "show_previews_for_long": False,
        }

        response = await alice_client.patch("/users/me/settings", json=update_payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == update_payload
        async with async_session_maker() as session:
            settings = (await session.scalars(select(UserSettings))).one()
            assert settings.locale == "en-US"
            assert settings.theme == "dark"
            assert settings.show_previews_for_long is False

    @pytest.mark.parametrize(
        ("initial_payload", "update_payload", "expected"),
        [
            pytest.param(
                {},
                {"locale": "fil-PH"},
                {"locale": "fil-PH", "theme": "system", "show_previews_for_long": True},
                id="three_letter_locale",
            ),
            pytest.param(
                {},
                {"theme": "light"},
                {"locale": "ru-RU", "theme": "light", "show_previews_for_long": True},
                id="light_theme",
            ),
            pytest.param(
                {"theme": "dark"},
                {"theme": "system"},
                {"locale": "ru-RU", "theme": "system", "show_previews_for_long": True},
                id="system_theme",
            ),
            pytest.param(
                {},
                {"show_previews_for_long": False},
                {"locale": "ru-RU", "theme": "system", "show_previews_for_long": False},
                id="disable_previews",
            ),
            pytest.param(
                {"show_previews_for_long": False},
                {"show_previews_for_long": True},
                {"locale": "ru-RU", "theme": "system", "show_previews_for_long": True},
                id="enable_previews",
            ),
        ],
    )
    async def test_updates_only_provided_setting(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        initial_payload: dict,
        update_payload: dict,
        expected: dict,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)
        if initial_payload:
            initial_response = await alice_client.patch(
                "/users/me/settings", json=initial_payload
            )
            assert initial_response.status_code == status.HTTP_200_OK

        response = await alice_client.patch("/users/me/settings", json=update_payload)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected
        async with async_session_maker() as session:
            settings = (await session.scalars(select(UserSettings))).one()
            assert settings.locale == expected["locale"]
            assert settings.theme == expected["theme"]
            assert settings.show_previews_for_long is expected["show_previews_for_long"]

    @pytest.mark.parametrize("payload", [{}, {"unknown": "value"}])
    async def test_rejects_empty_update_without_changing_settings(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        payload: dict,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch("/users/me/settings", json=payload)

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
                }
            ],
        }
        async with async_session_maker() as session:
            settings = (await session.scalars(select(UserSettings))).one()
            assert settings.locale == "ru-RU"
            assert settings.theme == "system"
            assert settings.show_previews_for_long is True

    @pytest.mark.parametrize("field", ["locale", "theme", "show_previews_for_long"])
    async def test_rejects_explicit_null_without_changing_settings(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        field: str,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        alice_client = await auth_client_factory(alice)

        response = await alice_client.patch("/users/me/settings", json={field: None})

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
            settings = (await session.scalars(select(UserSettings))).one()
            assert settings.locale == "ru-RU"
            assert settings.theme == "system"
            assert settings.show_previews_for_long is True

    @pytest.mark.parametrize(
        ("invalid_field", "invalid_value", "expected_detail"),
        [
            pytest.param(
                "locale",
                "RU-ru",
                {
                    "type": "string_pattern_mismatch",
                    "loc": ["body", "locale", "constrained-str"],
                    "msg": "String should match pattern '^[a-z]{2,3}-[A-Z]{2}$'",
                    "input": "RU-ru",
                    "ctx": {"pattern": "^[a-z]{2,3}-[A-Z]{2}$"},
                },
                id="invalid_locale",
            ),
            pytest.param(
                "theme",
                "auto",
                {
                    "type": "literal_error",
                    "loc": ["body", "theme", "literal['light','dark','system']"],
                    "msg": "Input should be 'light', 'dark' or 'system'",
                    "input": "auto",
                    "ctx": {"expected": "'light', 'dark' or 'system'"},
                },
                id="invalid_theme",
            ),
            pytest.param(
                "show_previews_for_long",
                "false",
                {
                    "type": "bool_type",
                    "loc": ["body", "show_previews_for_long", "bool"],
                    "msg": "Input should be a valid boolean",
                    "input": "false",
                },
                id="invalid_boolean_type",
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
            "locale": "en-US",
            "theme": "dark",
            invalid_field: invalid_value,
        }

        response = await alice_client.patch("/users/me/settings", json=payload)

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
            settings = (await session.scalars(select(UserSettings))).one()
            assert settings.locale == "ru-RU"
            assert settings.theme == "system"
            assert settings.show_previews_for_long is True

    async def test_rejects_unauthenticated_update_without_changing_settings(
        self,
        user_factory: UserFactory,
        client_factory: ClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        await user_factory(username="alice", email="alice@example.com")
        guest_client = await client_factory()

        response = await guest_client.patch(
            "/users/me/settings", json={"theme": "dark"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {
            "code": "ACCESS_TOKEN_NOT_FOUND",
            "message": "Not authorized",
        }
        async with async_session_maker() as session:
            settings = (await session.scalars(select(UserSettings))).one()
            assert settings.theme == "system"

    async def test_updates_only_current_users_settings(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        bob = await user_factory(username="bob", email="bob@example.com")
        alice_client = await auth_client_factory(alice)
        bob_client = await auth_client_factory(bob)

        response = await alice_client.patch(
            "/users/me/settings", json={"theme": "dark"}
        )
        bob_response = await bob_client.get("/users/me")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "locale": "ru-RU",
            "theme": "dark",
            "show_previews_for_long": True,
        }
        assert bob_response.status_code == status.HTTP_200_OK
        assert bob_response.json()["settings"] == {
            "locale": "ru-RU",
            "theme": "system",
            "show_previews_for_long": True,
        }
        async with async_session_maker() as session:
            settings = (await session.scalars(select(UserSettings))).all()
            assert len(settings) == 2
            assert {setting.theme for setting in settings} == {"dark", "system"}

    async def test_other_session_sees_updated_settings(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        first_client = await auth_client_factory(alice)
        second_client = await auth_client_factory(alice)
        before = await second_client.get("/users/me")
        assert before.status_code == status.HTTP_200_OK
        assert before.json()["settings"] == {
            "locale": "ru-RU",
            "theme": "system",
            "show_previews_for_long": True,
        }

        update = await first_client.patch(
            "/users/me/settings", json={"theme": "dark"}
        )
        after = await second_client.get("/users/me")

        assert update.status_code == status.HTTP_200_OK
        assert update.json() == {
            "locale": "ru-RU",
            "theme": "dark",
            "show_previews_for_long": True,
        }
        assert after.status_code == status.HTTP_200_OK
        assert after.json()["settings"] == {
            "locale": "ru-RU",
            "theme": "dark",
            "show_previews_for_long": True,
        }
