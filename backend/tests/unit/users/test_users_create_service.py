from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from asyncpg.exceptions import CheckViolationError, UniqueViolationError
from sqlalchemy.exc import IntegrityError

from app.users.errors import EmailAlreadyExistsError, UsernameAlreadyExistsError
from app.users.schemas import CreateUserRequest
from app.users.models import User, UserSettings
from tests.unit.users.cases import USER_UUID, USER_WITH_SETTINGS_DATA


class TestCreateUser:
    @pytest.fixture
    def password_hasher(self, monkeypatch):
        hasher = AsyncMock(return_value="hashed-password")
        monkeypatch.setattr("app.users.service.hash_password_async", hasher)
        return hasher

    @pytest.fixture
    def persisted_defaults(self, users_uow):
        async def populate_database_defaults():
            user = users_uow.user_repo.add.call_args.args[0]
            user.id = 42
            user.uuid = USER_UUID
            user.created_at = datetime(2020, 1, 1, 12, tzinfo=UTC)
            user.updated_at = datetime(2020, 1, 1, 13, tzinfo=UTC)
            if users_uow.user_settings_repo.add.called:
                settings = users_uow.user_settings_repo.add.call_args.args[0]
                settings.created_at = datetime(2020, 1, 1, 12, tzinfo=UTC)
                settings.updated_at = datetime(2020, 1, 1, 13, tzinfo=UTC)

        users_uow.flush.side_effect = populate_database_defaults

    async def test_creates_user_with_hashed_password_and_default_settings(
        self, users_domain_service, users_uow, users_cache, password_hasher, persisted_defaults,
    ):
        payload = CreateUserRequest(
            username="new-user", email="new@example.com", password="password123",
        )

        result = await users_domain_service.create_user(payload)

        assert result.model_dump(mode="json") == {
            **USER_WITH_SETTINGS_DATA,
            "username": "new-user", "email": "new@example.com",
            "hashed_password": "hashed-password",
        }
        password_hasher.assert_called_once_with("password123")
        users_uow.user_repo.add.assert_called_once()
        user = users_uow.user_repo.add.call_args.args[0]
        assert isinstance(user, User)
        assert (user.username, user.email, user.hashed_password) == (
            "new-user", "new@example.com", "hashed-password",
        )
        users_uow.user_settings_repo.add.assert_called_once()
        settings = users_uow.user_settings_repo.add.call_args.args[0]
        assert isinstance(settings, UserSettings)
        assert (settings.user_id, settings.locale, settings.theme, settings.show_previews_for_long) == (
            42, "ru-RU", "system", True,
        )
        users_uow.commit.assert_awaited_once()
        assert users_cache.mock_calls == []

    @pytest.mark.parametrize(
        ("constraint", "expected_error"),
        [
            ("uq_users_email", EmailAlreadyExistsError),
            ("uq_users_username_lower", UsernameAlreadyExistsError),
        ],
    )
    async def test_translates_known_unique_conflicts_and_preserves_cause(
        self, users_uow, users_domain_service, users_cache, password_hasher, constraint, expected_error,
    ):
        cause = UniqueViolationError("duplicate value")
        cause.constraint_name = constraint
        original = Exception("driver error")
        original.__cause__ = cause
        database_error = IntegrityError("INSERT", {}, original)
        users_uow.flush.side_effect = database_error
        payload = CreateUserRequest(
            username="new-user", email="new@example.com", password="password123",
        )

        with pytest.raises(expected_error) as error:
            await users_domain_service.create_user(payload)

        assert error.value.__cause__ is database_error
        users_uow.commit.assert_not_awaited()
        users_uow.user_settings_repo.add.assert_not_called()
        assert users_cache.mock_calls == []

    @pytest.mark.parametrize(
        ("cause_type", "constraint"),
        [
            (UniqueViolationError, "uq_users_uuid"),
            (UniqueViolationError, None),
            (CheckViolationError, "uq_users_email"),
            (Exception, None),
        ],
    )
    async def test_propagates_unexpected_integrity_error_unchanged(
        self, users_uow, users_domain_service, users_cache, password_hasher, cause_type, constraint,
    ):
        cause = cause_type("unexpected database failure")
        cause.constraint_name = constraint
        original = Exception("driver error")
        original.__cause__ = cause
        database_error = IntegrityError("INSERT", {}, original)
        users_uow.flush.side_effect = database_error
        payload = CreateUserRequest(
            username="new-user", email="new@example.com", password="password123",
        )

        with pytest.raises(IntegrityError) as error:
            await users_domain_service.create_user(payload)

        assert error.value is database_error
        users_uow.commit.assert_not_awaited()
        assert users_cache.mock_calls == []

    @pytest.mark.parametrize(
        ("constraint", "expected_error"),
        [
            ("uq_users_email", EmailAlreadyExistsError),
            ("uq_users_username_lower", UsernameAlreadyExistsError),
            ("uq_users_uuid", IntegrityError),
        ],
    )
    async def test_handles_integrity_failure_at_commit(
        self, users_domain_service, users_uow, users_cache, password_hasher,
        persisted_defaults, constraint, expected_error,
    ):
        cause = UniqueViolationError("duplicate value")
        cause.constraint_name = constraint
        original = Exception("driver error")
        original.__cause__ = cause
        database_error = IntegrityError("INSERT", {}, original)
        users_uow.commit.side_effect = database_error
        payload = CreateUserRequest(
            username="new-user", email="new@example.com", password="password123",
        )

        with pytest.raises(expected_error) as error:
            await users_domain_service.create_user(payload)

        if expected_error is IntegrityError:
            assert error.value is database_error
        else:
            assert error.value.__cause__ is database_error
        assert users_cache.mock_calls == []
