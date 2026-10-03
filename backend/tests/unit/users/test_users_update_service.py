import pytest
from asyncpg.exceptions import CheckViolationError, UniqueViolationError
from sqlalchemy.exc import IntegrityError

from app.errors import RequestValueError
from app.users.errors import EmailAlreadyExistsError, UsernameAlreadyExistsError
from app.users.schemas import UpdateUserRequest, UpdateUserSettingsRequest
from tests.unit.users.cases import SETTINGS_DATA, USER_WITH_SETTINGS_DATA


class TestUpdateUser:
    @pytest.mark.parametrize(
        "changes",
        [
            {"username": "updated-user"},
            {"email": "updated@example.com"},
            {"username": "updated-user", "email": "updated@example.com"},
        ],
    )
    async def test_updates_only_provided_fields_and_invalidates_after_commit(
        self, users_domain_service, users_uow, users_cache, users_entity, changes,
    ):
        users_entity.__dict__.update(changes)
        users_uow.user_repo.update_user.return_value = users_entity
        users_uow.commit.side_effect = lambda: users_cache.invalidate_users.assert_not_awaited()

        result = await users_domain_service.update_user(42, UpdateUserRequest(**changes))

        assert result.model_dump(mode="json") == {**USER_WITH_SETTINGS_DATA, **changes}
        users_uow.user_repo.update_user.assert_awaited_once_with(user_id=42, payload=changes)
        users_uow.flush.assert_awaited_once()
        users_uow.commit.assert_awaited_once()
        users_cache.invalidate_users.assert_awaited_once_with(user_ids=[42])
        users_cache.invalidate_users_settings.assert_not_awaited()

    async def test_rejects_empty_body_without_writing(
        self, users_domain_service, users_uow, users_cache,
    ):
        with pytest.raises(RequestValueError) as error:
            await users_domain_service.update_user(42, UpdateUserRequest())

        assert str(error.value) == "Update body is empty"
        assert error.value.failed_field == "body"
        users_uow.user_repo.update_user.assert_not_awaited()
        users_uow.flush.assert_not_awaited()
        users_uow.commit.assert_not_awaited()
        assert users_cache.mock_calls == []

    @pytest.mark.parametrize("stage", ["repository", "flush", "commit"])
    @pytest.mark.parametrize(
        ("constraint", "expected_error", "message"),
        [
            ("uq_users_email", EmailAlreadyExistsError, "Email is already in use"),
            ("uq_users_username_lower", UsernameAlreadyExistsError, "Username is already in use"),
        ],
    )
    async def test_translates_known_integrity_error_without_invalidating(
        self, users_domain_service, users_uow, users_cache, users_entity,
        stage, constraint, expected_error, message,
    ):
        cause = UniqueViolationError("duplicate value")
        cause.constraint_name = constraint
        original = Exception("driver error")
        original.__cause__ = cause
        database_error = IntegrityError("UPDATE", {}, original)
        users_uow.user_repo.update_user.return_value = users_entity
        failing_call = {
            "repository": users_uow.user_repo.update_user,
            "flush": users_uow.flush, "commit": users_uow.commit,
        }[stage]
        failing_call.side_effect = database_error

        with pytest.raises(expected_error, match=message) as error:
            await users_domain_service.update_user(42, UpdateUserRequest(username="updated-user"))

        assert error.value.__cause__ is database_error
        assert users_cache.mock_calls == []
        if stage != "commit":
            users_uow.commit.assert_not_awaited()

    @pytest.mark.parametrize(
        ("cause_type", "constraint"),
        [
            (UniqueViolationError, "uq_users_uuid"),
            (CheckViolationError, "uq_users_email"),
            (Exception, None),
        ],
    )
    async def test_propagates_unexpected_integrity_error(
        self, users_domain_service, users_uow, users_cache, cause_type, constraint,
    ):
        cause = cause_type("database failure")
        cause.constraint_name = constraint
        original = Exception("driver error")
        original.__cause__ = cause
        database_error = IntegrityError("UPDATE", {}, original)
        users_uow.user_repo.update_user.side_effect = database_error

        with pytest.raises(IntegrityError) as error:
            await users_domain_service.update_user(42, UpdateUserRequest(username="updated-user"))

        assert error.value is database_error
        users_uow.commit.assert_not_awaited()
        assert users_cache.mock_calls == []

    async def test_does_not_invalidate_when_commit_fails(
        self, users_domain_service, users_uow, users_cache, users_entity,
    ):
        users_uow.user_repo.update_user.return_value = users_entity
        users_uow.commit.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            await users_domain_service.update_user(42, UpdateUserRequest(email="updated@example.com"))

        assert users_cache.mock_calls == []


class TestUpdateUserSettings:
    @pytest.mark.parametrize(
        "changes",
        [
            {"locale": "fil-PH"}, {"theme": "dark"}, {"show_previews_for_long": False},
            {"locale": "en-US", "theme": "light", "show_previews_for_long": False},
        ],
    )
    async def test_preserves_partial_changes_and_false_and_invalidates_after_commit(
        self, users_domain_service, users_uow, users_cache, users_entity, changes,
    ):
        users_entity.settings.__dict__.update(changes)
        users_uow.user_settings_repo.update_user_settings.return_value = users_entity.settings
        users_uow.commit.side_effect = lambda: users_cache.invalidate_users_settings.assert_not_awaited()

        result = await users_domain_service.update_user_settings(42, UpdateUserSettingsRequest(**changes))

        assert result.model_dump(mode="json") == {**SETTINGS_DATA, **changes}
        users_uow.user_settings_repo.update_user_settings.assert_awaited_once_with(user_id=42, payload=changes)
        users_uow.flush.assert_awaited_once()
        users_uow.commit.assert_awaited_once()
        users_cache.invalidate_users_settings.assert_awaited_once_with(user_ids=[42])
        users_cache.invalidate_users.assert_not_awaited()

    async def test_rejects_empty_body_without_writing(
        self, users_domain_service, users_uow, users_cache,
    ):
        with pytest.raises(RequestValueError) as error:
            await users_domain_service.update_user_settings(42, UpdateUserSettingsRequest())

        assert str(error.value) == "Update body is empty"
        assert error.value.failed_field == "body"
        users_uow.user_settings_repo.update_user_settings.assert_not_awaited()
        users_uow.flush.assert_not_awaited()
        users_uow.commit.assert_not_awaited()
        assert users_cache.mock_calls == []

    @pytest.mark.parametrize("stage", ["repository", "flush", "commit"])
    async def test_propagates_database_failure_without_invalidating(
        self, users_domain_service, users_uow, users_cache, users_entity, stage,
    ):
        users_uow.user_settings_repo.update_user_settings.return_value = users_entity.settings
        failing_call = {
            "repository": users_uow.user_settings_repo.update_user_settings,
            "flush": users_uow.flush, "commit": users_uow.commit,
        }[stage]
        failing_call.side_effect = RuntimeError("database failed")

        with pytest.raises(RuntimeError, match="database failed"):
            await users_domain_service.update_user_settings(42, UpdateUserSettingsRequest(theme="dark"))

        assert users_cache.mock_calls == []
        if stage != "commit":
            users_uow.commit.assert_not_awaited()
