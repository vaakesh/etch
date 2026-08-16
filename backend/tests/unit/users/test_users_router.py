from unittest.mock import AsyncMock
import pytest_asyncio
import pytest
from httpx import AsyncClient

from app.users.schemas import PrivateUserResponse, UserSettingsResponse, UserSettingsUpdate
from fastapi import status

from tests.unit.factories import make_user_settings

class TestGetMe:
    async def test_returns_current_user(
        self,
        client: AsyncClient,
        current_user,
        user_settings,
        user_service: AsyncMock,
    ):
        user_service.get_user_settings_by_id.return_value = (
            user_settings
        )

        response = await client.get("/users/me")

        assert response.status_code == status.HTTP_200_OK
        expected = PrivateUserResponse(
            uuid=current_user.uuid,
            username=current_user.username,
            email=current_user.email,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            settings=UserSettingsResponse(
                locale=user_settings.locale,
                theme=user_settings.theme,
                show_previews_for_long=(
                    user_settings.show_previews_for_long
                ),
            ),
        )

        assert response.json() == expected.model_dump(mode="json")
        
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
        user_service.get_user_settings_by_id.return_value = (
            user_settings
        )

        response = await client.get("/users/me")

        assert response.status_code == status.HTTP_200_OK

        expected = PrivateUserResponse(
            uuid=current_user.uuid,
            username=current_user.username,
            email=current_user.email,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            settings=UserSettingsResponse(
                locale=user_settings.locale,
                theme=user_settings.theme,
                show_previews_for_long=(
                    user_settings.show_previews_for_long
                ),
            ),
        )

        assert response.json() == expected.model_dump(mode="json")

        user_service.get_user_settings_by_id.assert_awaited_once_with(
            user_id=current_user.id,
            for_update=False,
        )


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

        user_service.update_user_settings.return_value = (
            updated_user_settings
        )

        response = await client.patch(
            "/users/me/settings",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK

        expected = UserSettingsResponse.model_validate(
            updated_user_settings
        )

        assert response.json() == expected.model_dump(
            mode="json"
        )

        user_service.update_user_settings.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UserSettingsUpdate(**payload),
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"locale": "ru-RU"},
            {"locale": "en-US"},
            {"theme": "dark"},
            {"theme": "light"},
            {"theme": "system"},
            {"show_previews_for_long": True},
            {"show_previews_for_long": False},
        ],
    )
    async def test_updates_single_setting(
        self,
        client: AsyncClient,
        current_user,
        payload,
        user_service: AsyncMock,
    ):
        updated_settings = make_user_settings(**payload)

        user_service.update_user_settings.return_value = (
            updated_settings
        )

        response = await client.patch(
            "/users/me/settings",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK

        expected = UserSettingsResponse.model_validate(
            updated_settings
        )

        assert response.json() == expected.model_dump(
            mode="json"
        )

        user_service.update_user_settings.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UserSettingsUpdate(**payload),
        )

    async def test_accepts_empty_payload(
        self,
        client: AsyncClient,
        current_user,
        user_service: AsyncMock,
    ):
        payload = {}
        updated_user_settings = make_user_settings(**payload)

        user_service.update_user_settings.return_value = (
            updated_user_settings
        )

        response = await client.patch(
            "/users/me/settings",
            json=payload,
        )

        assert response.status_code == status.HTTP_200_OK

        expected = UserSettingsResponse.model_validate(
            updated_user_settings
        )

        assert response.json() == expected.model_dump(
            mode="json"
        )

        user_service.update_user_settings.assert_awaited_once_with(
            current_user_id=current_user.id,
            payload=UserSettingsUpdate(**payload),
        )


