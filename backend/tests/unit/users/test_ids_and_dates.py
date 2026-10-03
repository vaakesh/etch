from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.errors import RequestValueError
from app.users.schemas import InternalUser, InternalUserSettings, InternalUserWithSettings, PrivateUserResponse, UserProfileResponse
from tests.unit.factories import make_user, make_user_settings


def make_internal_settings(**overrides):
    return make_user_settings(**{
        "user_id": 42,
        "created_at": datetime(2020, 1, 1, 12, tzinfo=UTC),
        "updated_at": datetime(2020, 1, 1, 13, tzinfo=UTC),
        **overrides,
    })


class TestUserIds:
    @pytest.mark.parametrize("value", [0, -1])
    @pytest.mark.parametrize("schema, factory, field", [
        (InternalUser, make_user, "id"),
        (InternalUserWithSettings, make_user, "id"),
        (InternalUserSettings, make_internal_settings, "user_id"),
    ])
    def test_rejects_nonpositive_id(self, value, schema, factory, field):
        obj = factory(**{field: value}, settings=make_internal_settings())

        with pytest.raises(ValidationError) as error:
            schema.model_validate(obj)

        assert error.value.errors()[0]["loc"] == (field,)
        assert error.value.errors()[0]["type"] == "greater_than_equal"

    @pytest.mark.parametrize("schema, factory, field", [
        (InternalUser, make_user, "id"),
        (InternalUserWithSettings, make_user, "id"),
        (InternalUserSettings, make_internal_settings, "user_id"),
    ])
    def test_accepts_smallest_positive_id(self, schema, factory, field):
        obj = factory(**{field: 1}, settings=make_internal_settings())

        result = schema.model_validate(obj)

        assert getattr(result, field) == 1


class TestUserUuid:
    @pytest.mark.parametrize("schema", [InternalUser, InternalUserWithSettings, PrivateUserResponse, UserProfileResponse])
    @pytest.mark.parametrize("value", [
        "0198ad01-b200-4000-8000-000000000042",
        "0198ad01-b200-7000-0000-000000000042",
    ])
    def test_rejects_wrong_version_or_variant(self, schema, value):
        obj = make_user(uuid=UUID(value), settings=make_internal_settings(), deck_count=0, total_saves_count=0)

        with pytest.raises(ValidationError) as error:
            schema.model_validate(obj)

        assert error.value.errors()[0]["loc"] == ("uuid",)
        assert error.value.errors()[0]["type"] == "uuid_version"

    @pytest.mark.parametrize("schema", [InternalUser, InternalUserWithSettings, PrivateUserResponse, UserProfileResponse])
    def test_accepts_uuid_v7(self, schema):
        obj = make_user(settings=make_internal_settings(), deck_count=0, total_saves_count=0)

        result = schema.model_validate(obj)

        assert result.uuid == UUID("0198ad01-b200-7000-8000-000000000042")


class TestUserDates:
    @pytest.mark.parametrize("schema, factory", [
        (InternalUser, make_user),
        (InternalUserWithSettings, make_user),
        (InternalUserSettings, make_internal_settings),
        (PrivateUserResponse, make_user),
    ])
    @pytest.mark.parametrize("hour", [12, 13])
    def test_accepts_equal_or_later_update(self, schema, factory, hour):
        obj = factory(
            created_at=datetime(2020, 1, 1, 12, tzinfo=UTC),
            updated_at=datetime(2020, 1, 1, hour, tzinfo=UTC),
            settings=make_internal_settings(),
        )

        result = schema.model_validate(obj)

        assert result.updated_at == datetime(2020, 1, 1, hour, tzinfo=UTC)

    @pytest.mark.parametrize("schema, factory", [
        (InternalUser, make_user),
        (InternalUserWithSettings, make_user),
        (InternalUserSettings, make_internal_settings),
        (PrivateUserResponse, make_user),
    ])
    def test_rejects_update_before_creation(self, schema, factory):
        obj = factory(
            created_at=datetime(2020, 1, 1, 12, tzinfo=UTC),
            updated_at=datetime(2020, 1, 1, 11, tzinfo=UTC),
            settings=make_internal_settings(),
        )

        with pytest.raises(RequestValueError) as error:
            schema.model_validate(obj)

        assert error.value.failed_field == "updated_at"
        assert str(error.value) == "updated_at must be greater than or equal to created_at"

    @pytest.mark.parametrize("schema", [InternalUser, InternalUserWithSettings, PrivateUserResponse])
    @pytest.mark.parametrize("naive_field", ["created_at", "updated_at"])
    def test_rejects_incompatible_timezone_information(self, schema, naive_field):
        timestamps = {
            "created_at": datetime(2020, 1, 1, 12, tzinfo=UTC),
            "updated_at": datetime(2020, 1, 1, 13, tzinfo=UTC),
        }
        timestamps[naive_field] = timestamps[naive_field].replace(tzinfo=None)
        obj = make_user(**timestamps, settings=make_internal_settings())

        with pytest.raises(RequestValueError) as error:
            schema.model_validate(obj)

        assert error.value.failed_field == "updated_at"
        assert str(error.value) == "Dates must have compatible timezone information"

    @pytest.mark.parametrize("schema, factory", [
        (InternalUser, make_user),
        (InternalUserWithSettings, make_user),
        (InternalUserSettings, make_internal_settings),
        (PrivateUserResponse, make_user),
    ])
    @pytest.mark.parametrize("field", ["created_at", "updated_at"])
    def test_rejects_future_timestamp(self, schema, factory, field):
        obj = factory(**{field: datetime(2099, 1, 1, tzinfo=UTC)}, settings=make_internal_settings())

        with pytest.raises(ValidationError) as error:
            schema.model_validate(obj)

        assert error.value.errors()[0]["loc"] == (field,)
        assert error.value.errors()[0]["type"] == "datetime_past"
