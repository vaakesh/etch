import pytest
from pydantic import ValidationError

from app.errors import RequestValueError
from app.users.schemas import UpdateUserSettingsRequest


class TestUpdateUserSettingsRequest:
    @pytest.mark.parametrize("locale", ["ru-RU", "en-US", "es-ES", "ja-JP", "zh-CN", "fil-PH"])
    def test_accepts_locale_format_without_language_allowlist(self, locale):
        payload = UpdateUserSettingsRequest(locale=locale)

        assert payload.model_dump(exclude_unset=True) == {"locale": locale}

    @pytest.mark.parametrize("locale", ["ru", "ru-ru", "RU-RU", "r-RU", "abcd-US", "ru_RU", " ru-RU", "ru-RU\n", "fil-PH\n", "zh-Hans-CN", "en-001"])
    def test_rejects_invalid_locale_format(self, locale):
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(locale=locale)

    @pytest.mark.parametrize("theme", ["light", "dark", "system"])
    def test_accepts_supported_theme(self, theme):
        payload = UpdateUserSettingsRequest(theme=theme)

        assert payload.model_dump(exclude_unset=True) == {"theme": theme}

    @pytest.mark.parametrize("theme", ["", "auto", "Dark", " dark "])
    def test_rejects_unsupported_theme(self, theme):
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(theme=theme)

    @pytest.mark.parametrize("value", [True, False])
    def test_preserves_boolean_in_partial_update(self, value):
        payload = UpdateUserSettingsRequest(show_previews_for_long=value)

        assert payload.model_dump(exclude_unset=True) == {"show_previews_for_long": value}

    @pytest.mark.parametrize("value", [0, 1, "true", "false", "0", "1"])
    def test_rejects_boolean_coercion(self, value):
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(show_previews_for_long=value)

    def test_omitted_fields_are_excluded_from_update(self):
        payload = UpdateUserSettingsRequest()

        assert payload.model_dump(exclude_unset=True) == {}

    @pytest.mark.parametrize("field", ["locale", "theme", "show_previews_for_long"])
    def test_rejects_explicit_null(self, field):
        with pytest.raises(RequestValueError) as error:
            UpdateUserSettingsRequest.model_validate({field: None})

        assert error.value.failed_field == field
        assert str(error.value) == "Field must not be null"


class TestUpdateSettingsValidation:
    @pytest.mark.parametrize(
        ("payload", "expected_details"),
        [
            (
                {"locale": "ru"},
                [
                    {
                        "type": "string_too_short",
                        "loc": ["body", "locale", "constrained-str"],
                        "msg": "String should have at least 5 characters",
                        "input": "ru", "ctx": {"min_length": 5},
                    },
                    {
                        "type": "none_required", "loc": ["body", "locale", "none"],
                        "msg": "Input should be None", "input": "ru",
                    },
                ],
            ),
            (
                {"theme": "auto"},
                [
                    {
                        "type": "literal_error",
                        "loc": ["body", "theme", "literal['light','dark','system']"],
                        "msg": "Input should be 'light', 'dark' or 'system'",
                        "input": "auto", "ctx": {"expected": "'light', 'dark' or 'system'"},
                    },
                    {
                        "type": "none_required", "loc": ["body", "theme", "none"],
                        "msg": "Input should be None", "input": "auto",
                    },
                ],
            ),
            (
                {"show_previews_for_long": "false"},
                [
                    {
                        "type": "bool_type", "loc": ["body", "show_previews_for_long", "bool"],
                        "msg": "Input should be a valid boolean", "input": "false",
                    },
                    {
                        "type": "none_required", "loc": ["body", "show_previews_for_long", "none"],
                        "msg": "Input should be None", "input": "false",
                    },
                ],
            ),
        ],
        ids=["invalid_locale", "invalid_theme", "coerced_boolean"],
    )
    async def test_rejects_invalid_field_before_calling_service(
        self, client, user_service, payload, expected_details,
    ):
        response = await client.patch("/users/me/settings", json=payload)

        assert response.status_code == 422
        assert response.json() == {
            "code": "VALIDATION_ERROR", "message": "Validation error",
            "details": expected_details,
        }
        user_service.update_user_settings.assert_not_awaited()

    @pytest.mark.parametrize("field", ["locale", "theme", "show_previews_for_long"])
    async def test_api_rejects_null_before_calling_service(self, client, user_service, field):
        response = await client.patch("/users/me/settings", json={field: None})

        assert response.status_code == 422
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {"type": "value_error", "loc": ["body", field], "msg": "Field must not be null", "input": None},
            ],
        }
        user_service.update_user_settings.assert_not_awaited()
