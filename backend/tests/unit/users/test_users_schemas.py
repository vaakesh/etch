import pytest
from pydantic import ValidationError

from app.errors import RequestValueError
from app.users.schemas import UpdateUserRequest, UserProfileResponse


class TestUpdateUserRequest:
    def test_omitted_fields_are_excluded_from_update(self):
        payload = UpdateUserRequest()

        assert payload.model_dump(exclude_unset=True) == {}
        assert payload.model_fields_set == set()

    @pytest.mark.parametrize(
        "changes",
        [
            {"username": "Alice"}, {"email": "alice@example.com"},
            {"username": "Alice", "email": "alice@example.com"},
        ],
    )
    def test_preserves_only_provided_fields(self, changes):
        payload = UpdateUserRequest(**changes)

        assert payload.model_dump(exclude_unset=True) == changes
        assert payload.model_fields_set == set(changes)

    def test_normalizes_all_related_fields(self):
        payload = UpdateUserRequest(username=" \tAlice-01_\n", email=" \tALICE@EXAMPLE.COM\n")

        assert payload.model_dump(exclude_unset=True) == {
            "username": "Alice-01_", "email": "alice@example.com",
        }

    @pytest.mark.parametrize("field", ["username", "email"])
    def test_rejects_explicit_null(self, field):
        with pytest.raises(RequestValueError) as error:
            UpdateUserRequest.model_validate({field: None})

        assert str(error.value) == "Field must not be null"
        assert error.value.failed_field == field


class TestUserProfileResponse:
    @pytest.mark.parametrize("field", ["deck_count", "total_saves_count"])
    def test_rejects_negative_counter(self, users_entity, field):
        data = {
            "uuid": users_entity.uuid, "username": "test-user",
            "created_at": users_entity.created_at, "deck_count": 0, "total_saves_count": 0,
            field: -1,
        }

        with pytest.raises(ValidationError) as error:
            UserProfileResponse(**data)

        assert error.value.errors()[0]["loc"] == (field,)
        assert error.value.errors()[0]["type"] == "greater_than_equal"
