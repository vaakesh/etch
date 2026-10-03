from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, call, create_autospec
from uuid import UUID

import pytest

from app.auth.errors import InvalidLoginCredentials, InvalidRefreshTokenError
from app.auth.repository import AuthRepository
from app.auth.schemas import AccessTokenResponse, IssuedTokens, TokenPair
from app.auth.service import AuthService, AuthTokensService
from app.service import UnitOfWork
from app.users.errors import UserNotFoundError
from app.users.repository import UserRepository
from tests.unit.factories import make_user, make_user_session


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def auth_context(monkeypatch):
    uow = create_autospec(UnitOfWork, instance=True)
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = False
    uow.user_repo = create_autospec(UserRepository, instance=True)
    uow.auth_repo = create_autospec(AuthRepository, instance=True)
    user = make_user()
    session = make_user_session(
        uuid=UUID("0198ad01-b200-7000-8000-000000000600"),
        refresh_token_hash="a" * 64,
    )
    uow.user_repo.get_by_username.return_value = user
    uow.user_repo.get_by_id.return_value = user
    uow.auth_repo.get_user_id_by_refresh.return_value = user.id
    uow.auth_repo.get_user_session_by_refresh.return_value = session

    tokens = create_autospec(AuthTokensService, instance=True)
    tokens.config = SimpleNamespace(refresh_token_expire_days=7)
    tokens.issue_tokens.return_value = IssuedTokens(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        refresh_token_hash="b" * 64,
    )
    tokens.create_access_token.return_value = "bearer-access-token"
    tokens.hash_refresh_token.return_value = "a" * 64
    verify = Mock(return_value=True)
    hash_password = Mock(return_value="new-password-hash")
    monkeypatch.setattr("app.auth.service.verify_password", verify)
    monkeypatch.setattr("app.auth.service.hash_password", hash_password)
    monkeypatch.setattr("app.auth.service.utcnow", lambda: NOW)
    factory = Mock(return_value=uow)
    service = AuthService(uow_factory=factory, auth_tokens_service=tokens)
    return SimpleNamespace(
        service=service, uow=uow, factory=factory, tokens=tokens,
        user=user, session=session, verify=verify, hash_password=hash_password,
    )


class TestLogin:
    async def test_returns_tokens_and_commits_session_with_hashed_refresh_token(
        self, auth_context,
    ):
        ctx = auth_context
        calls = Mock()
        calls.attach_mock(ctx.uow.user_repo.get_by_username, "lock_user")
        calls.attach_mock(ctx.verify, "verify_password")
        calls.attach_mock(ctx.uow.auth_repo.add, "add_session")

        result = await ctx.service.login("test-user", "password123")

        assert result == TokenPair("new-access-token", "new-refresh-token")
        ctx.uow.user_repo.get_by_username.assert_awaited_once_with(
            username="test-user", for_update=True,
        )
        ctx.verify.assert_called_once_with("password123", "hashed-test-password")
        ctx.tokens.issue_tokens.assert_called_once_with(user_uuid=ctx.user.uuid)
        ctx.uow.auth_repo.add.assert_called_once()
        session = ctx.uow.auth_repo.add.call_args.kwargs["user_session"]
        assert session.user_id == 42
        assert session.refresh_token_hash == "b" * 64
        assert session.expires_at == datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
        assert session.revoked_at is None
        assert session.replaced_by_session_id is None
        assert calls.mock_calls == [
            call.lock_user(username="test-user", for_update=True),
            call.verify_password("password123", "hashed-test-password"),
            call.add_session(user_session=session),
        ]
        ctx.uow.commit.assert_awaited_once_with()

    @pytest.mark.parametrize("scenario", ["user-missing", "wrong-password"])
    async def test_rejects_credentials_without_issuing_tokens_or_committing(
        self, auth_context, scenario,
    ):
        ctx = auth_context
        if scenario == "user-missing":
            ctx.uow.user_repo.get_by_username.return_value = None
        else:
            ctx.verify.return_value = False

        with pytest.raises(InvalidLoginCredentials, match="Invalid username or password"):
            await ctx.service.login("test-user", "wrong-password")

        ctx.tokens.issue_tokens.assert_not_called()
        ctx.uow.auth_repo.add.assert_not_called()
        ctx.uow.commit.assert_not_awaited()

    async def test_propagates_commit_failure_without_returning_tokens(self, auth_context):
        ctx = auth_context
        ctx.uow.commit.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            await ctx.service.login("test-user", "password123")

        ctx.uow.__aexit__.assert_awaited_once()


class TestLoginByBearerTokenWithoutRefresh:
    async def test_returns_access_token_without_creating_refresh_session(self, auth_context):
        ctx = auth_context

        result = await ctx.service.login_by_bearer_token_without_refresh(
            "test-user", "password123",
        )

        assert result == AccessTokenResponse("bearer-access-token", "Bearer")
        ctx.uow.user_repo.get_by_username.assert_awaited_once_with(
            username="test-user", for_update=False,
        )
        ctx.verify.assert_called_once_with("password123", "hashed-test-password")
        ctx.tokens.create_access_token.assert_called_once_with(ctx.user.uuid)
        ctx.tokens.issue_tokens.assert_not_called()
        ctx.uow.auth_repo.add.assert_not_called()
        ctx.uow.commit.assert_not_awaited()

    @pytest.mark.parametrize("scenario", ["user-missing", "wrong-password"])
    async def test_rejects_invalid_credentials_without_creating_access_token(
        self, auth_context, scenario,
    ):
        ctx = auth_context
        if scenario == "user-missing":
            ctx.uow.user_repo.get_by_username.return_value = None
        else:
            ctx.verify.return_value = False

        with pytest.raises(InvalidLoginCredentials):
            await ctx.service.login_by_bearer_token_without_refresh("test-user", "wrong-password")

        ctx.tokens.create_access_token.assert_not_called()
        ctx.uow.commit.assert_not_awaited()


class TestRefresh:
    async def test_rotates_session_and_revokes_old_session_before_commit(self, auth_context):
        ctx = auth_context
        calls = Mock()
        calls.attach_mock(ctx.uow.auth_repo.get_user_id_by_refresh, "find_owner")
        calls.attach_mock(ctx.uow.user_repo.get_by_id, "lock_user")
        calls.attach_mock(ctx.uow.auth_repo.get_user_session_by_refresh, "lock_session")

        async def assign_session_id():
            new_session = ctx.uow.auth_repo.add.call_args.args[0]
            new_session.id = 601

        async def check_rotation_at_commit():
            assert ctx.session.replaced_by_session_id == 601
            assert ctx.session.revoked_at == NOW

        ctx.uow.auth_repo.flush.side_effect = assign_session_id
        ctx.uow.commit.side_effect = check_rotation_at_commit

        result = await ctx.service.refresh("old-refresh-token")

        assert result == TokenPair("new-access-token", "new-refresh-token")
        ctx.tokens.hash_refresh_token.assert_called_once_with("old-refresh-token")
        ctx.uow.auth_repo.get_user_session_by_refresh.assert_awaited_once_with(
            "a" * 64, for_update=True,
        )
        assert calls.mock_calls == [
            call.find_owner("a" * 64),
            call.lock_user(user_id=42, for_update=True),
            call.lock_session("a" * 64, for_update=True),
        ]
        ctx.tokens.issue_tokens.assert_called_once_with(ctx.user.uuid)
        ctx.uow.auth_repo.add.assert_called_once()
        new_session = ctx.uow.auth_repo.add.call_args.args[0]
        assert new_session.user_id == 42
        assert new_session.refresh_token_hash == "b" * 64
        assert new_session.expires_at == datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
        ctx.uow.commit.assert_awaited_once_with()

    @pytest.mark.parametrize(
        "session",
        [
            pytest.param(None, id="session-deleted-after-owner-lookup"),
            pytest.param(make_user_session(revoked_at=NOW), id="revoked-session"),
            pytest.param(make_user_session(replaced_by_session_id=601), id="replaced-session"),
            pytest.param(make_user_session(expires_at=NOW), id="expires-now"),
            pytest.param(make_user_session(expires_at=NOW - timedelta(seconds=1)), id="expired"),
        ],
    )
    async def test_rejects_invalid_session_without_issuing_tokens(self, auth_context, session):
        ctx = auth_context
        ctx.uow.auth_repo.get_user_session_by_refresh.return_value = session

        with pytest.raises(InvalidRefreshTokenError, match="Session expired"):
            await ctx.service.refresh("invalid-refresh-token")

        ctx.uow.user_repo.get_by_id.assert_awaited_once_with(user_id=42, for_update=True)
        ctx.tokens.issue_tokens.assert_not_called()
        ctx.uow.auth_repo.add.assert_not_called()
        ctx.uow.commit.assert_not_awaited()

    async def test_rejects_unknown_token_without_locking_user_or_session(self, auth_context):
        ctx = auth_context
        ctx.uow.auth_repo.get_user_id_by_refresh.return_value = None

        with pytest.raises(InvalidRefreshTokenError, match="Session expired"):
            await ctx.service.refresh("unknown-refresh-token")

        ctx.uow.user_repo.get_by_id.assert_not_awaited()
        ctx.uow.auth_repo.get_user_session_by_refresh.assert_not_awaited()
        ctx.tokens.issue_tokens.assert_not_called()
        ctx.uow.auth_repo.add.assert_not_called()
        ctx.uow.commit.assert_not_awaited()

    async def test_rejects_session_revoked_while_waiting_for_user_lock(self, auth_context):
        ctx = auth_context

        async def lock_user(*, user_id, for_update):
            ctx.session.revoked_at = NOW
            return ctx.user

        ctx.uow.user_repo.get_by_id.side_effect = lock_user

        with pytest.raises(InvalidRefreshTokenError, match="Session expired"):
            await ctx.service.refresh("revoked-refresh-token")

        ctx.uow.auth_repo.get_user_session_by_refresh.assert_awaited_once_with(
            "a" * 64, for_update=True,
        )
        ctx.tokens.issue_tokens.assert_not_called()
        ctx.uow.auth_repo.add.assert_not_called()
        ctx.uow.commit.assert_not_awaited()

    async def test_accepts_session_expiring_one_second_later(self, auth_context):
        ctx = auth_context
        ctx.session.expires_at = NOW + timedelta(seconds=1)

        result = await ctx.service.refresh("active-refresh-token")

        assert result == TokenPair("new-access-token", "new-refresh-token")
        ctx.uow.commit.assert_awaited_once_with()

    async def test_raises_when_session_user_is_missing_without_revoking_session(self, auth_context):
        ctx = auth_context
        ctx.uow.user_repo.get_by_id.return_value = None

        with pytest.raises(UserNotFoundError):
            await ctx.service.refresh("active-refresh-token")

        ctx.uow.auth_repo.get_user_session_by_refresh.assert_not_awaited()
        assert ctx.session.revoked_at is None
        assert ctx.session.replaced_by_session_id is None
        ctx.tokens.issue_tokens.assert_not_called()
        ctx.uow.auth_repo.add.assert_not_called()
        ctx.uow.commit.assert_not_awaited()


class TestChangePassword:
    async def test_changes_hash_and_revokes_all_active_sessions(self, auth_context):
        ctx = auth_context

        await ctx.service.change_password(42, "old-password", "new-password")

        ctx.uow.user_repo.get_by_id.assert_awaited_once_with(user_id=42, for_update=True)
        ctx.verify.assert_called_once_with(
            password="old-password", password_hash="hashed-test-password",
        )
        ctx.hash_password.assert_called_once_with(password="new-password")
        assert ctx.user.hashed_password == "new-password-hash"
        ctx.uow.auth_repo.revoke_all_active_sessions_by_user_id.assert_awaited_once_with(
            user_id=42, revoked_at=NOW,
        )
        ctx.uow.commit.assert_awaited_once_with()

    @pytest.mark.parametrize("scenario", ["user-missing", "wrong-password"])
    async def test_rejects_credentials_without_changing_hash_or_revoking_sessions(
        self, auth_context, scenario,
    ):
        ctx = auth_context
        if scenario == "user-missing":
            ctx.uow.user_repo.get_by_id.return_value = None
        else:
            ctx.verify.return_value = False

        with pytest.raises(InvalidLoginCredentials):
            await ctx.service.change_password(42, "wrong-password", "new-password")

        assert ctx.user.hashed_password == "hashed-test-password"
        ctx.hash_password.assert_not_called()
        ctx.uow.auth_repo.revoke_all_active_sessions_by_user_id.assert_not_awaited()
        ctx.uow.commit.assert_not_awaited()

    async def test_does_not_commit_when_session_revocation_fails(self, auth_context):
        ctx = auth_context
        ctx.uow.auth_repo.revoke_all_active_sessions_by_user_id.side_effect = RuntimeError(
            "revocation failed",
        )

        with pytest.raises(RuntimeError, match="revocation failed"):
            await ctx.service.change_password(42, "old-password", "new-password")

        ctx.uow.commit.assert_not_awaited()


class TestLogout:
    @pytest.mark.parametrize("refresh_token", [None, ""])
    async def test_does_not_open_transaction_without_refresh_token(self, auth_context, refresh_token):
        ctx = auth_context

        result = await ctx.service.logout(refresh_token)

        assert result is None
        ctx.factory.assert_not_called()
        ctx.tokens.hash_refresh_token.assert_not_called()

    async def test_revokes_active_session_and_commits(self, auth_context):
        ctx = auth_context
        calls = Mock()
        calls.attach_mock(ctx.uow.auth_repo.get_user_id_by_refresh, "find_owner")
        calls.attach_mock(ctx.uow.user_repo.get_by_id, "lock_user")
        calls.attach_mock(ctx.uow.auth_repo.revoke_active_session_by_refresh_token_hash, "revoke_session")
        ctx.uow.auth_repo.revoke_active_session_by_refresh_token_hash.return_value = True

        result = await ctx.service.logout("active-refresh-token")

        assert result is None
        ctx.tokens.hash_refresh_token.assert_called_once_with("active-refresh-token")
        ctx.uow.auth_repo.revoke_active_session_by_refresh_token_hash.assert_awaited_once_with(
            refresh_token_hash="a" * 64, revoked_at=NOW,
        )
        ctx.uow.commit.assert_awaited_once_with()
        assert calls.mock_calls == [
            call.find_owner("a" * 64),
            call.lock_user(user_id=42, for_update=True),
            call.revoke_session(refresh_token_hash="a" * 64, revoked_at=NOW),
        ]

    async def test_does_not_commit_when_no_active_session_matches(self, auth_context):
        ctx = auth_context
        ctx.uow.auth_repo.revoke_active_session_by_refresh_token_hash.return_value = False

        result = await ctx.service.logout("inactive-refresh-token")

        assert result is None
        ctx.uow.auth_repo.revoke_active_session_by_refresh_token_hash.assert_awaited_once_with(
            refresh_token_hash="a" * 64, revoked_at=NOW,
        )
        ctx.uow.commit.assert_not_awaited()

    async def test_does_not_lock_user_or_update_sessions_for_unknown_token(self, auth_context):
        ctx = auth_context
        ctx.uow.auth_repo.get_user_id_by_refresh.return_value = None

        result = await ctx.service.logout("unknown-refresh-token")

        assert result is None
        ctx.uow.user_repo.get_by_id.assert_not_awaited()
        ctx.uow.auth_repo.revoke_active_session_by_refresh_token_hash.assert_not_awaited()
        ctx.uow.commit.assert_not_awaited()

    async def test_does_not_update_sessions_when_user_was_deleted(self, auth_context):
        ctx = auth_context
        ctx.uow.user_repo.get_by_id.return_value = None

        result = await ctx.service.logout("deleted-user-refresh-token")

        assert result is None
        ctx.uow.user_repo.get_by_id.assert_awaited_once_with(user_id=42, for_update=True)
        ctx.uow.auth_repo.revoke_active_session_by_refresh_token_hash.assert_not_awaited()
        ctx.uow.commit.assert_not_awaited()


class TestGetAllUserSessions:
    async def test_returns_user_sessions(self, auth_context):
        ctx = auth_context
        ctx.uow.auth_repo.get_all_user_sessions.return_value = [ctx.session]

        result = await ctx.service.get_all_user_sessions(42)

        assert result == [ctx.session]
        ctx.uow.auth_repo.get_all_user_sessions.assert_awaited_once_with(42)
        ctx.uow.commit.assert_not_awaited()

    async def test_returns_empty_list_when_user_has_no_sessions(self, auth_context):
        ctx = auth_context
        ctx.uow.auth_repo.get_all_user_sessions.return_value = []

        result = await ctx.service.get_all_user_sessions(42)

        assert result == []
        ctx.uow.auth_repo.get_all_user_sessions.assert_awaited_once_with(42)


class TestBuildUserSession:
    async def test_uses_configured_expiration_and_stores_refresh_hash(self, auth_context):
        ctx = auth_context
        ctx.tokens.config.refresh_token_expire_days = 2

        result = await ctx.service.build_user_session(ctx.user, "c" * 64)

        assert result.user_id == 42
        assert result.refresh_token_hash == "c" * 64
        assert result.expires_at == datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        assert result.revoked_at is None
        assert result.replaced_by_session_id is None
        ctx.factory.assert_not_called()
