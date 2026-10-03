import pytest
from pydantic import ValidationError

from app.users.schemas import InternalUser, InternalUserWithSettings
from tests.unit.factories import make_user, make_user_settings


class TestPasswordHash:
    @pytest.fixture(params=[InternalUser, InternalUserWithSettings])
    def schema(self, request):
        return request.param

    @pytest.fixture
    def user(self):
        user = make_user()
        user.settings = make_user_settings(
            user_id=user.id, created_at=user.created_at, updated_at=user.updated_at,
        )
        return user

    @pytest.mark.parametrize("value", ["x", "A" * 255, "$argon2id$v=19$m=65536,t=3,p=4$SaLt$HaSh"])
    def test_accepts_hash_without_changing_it(self, schema, user, value):
        user.hashed_password = value

        result = schema.model_validate(user)

        assert result.hashed_password == value

    @pytest.mark.parametrize("value", ["", "x" * 256, " hash", "hash ", "ha sh", "ha\tsh", "ha\nsh", "hash\n", None])
    def test_rejects_invalid_hash(self, schema, user, value):
        user.hashed_password = value

        with pytest.raises(ValidationError) as error:
            schema.model_validate(user)

        assert error.value.errors()[0]["loc"] == ("hashed_password",)
