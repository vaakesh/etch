


import hashlib
import hmac
import secrets
from collections.abc import Callable
from app.tracing import traced
from datetime import timedelta
from typing import Any
from uuid import UUID

import jwt
from app.auth.errors import (
    InvalidLoginCredentials,
    InvalidRefreshTokenError,
    InvalidTokenError,
    InvalidTokenTypeError,
)
from app.auth.models import UserSession
from app.auth.schemas import (
    AccessTokenResponse,
    IssuedTokens,
    TokenPair,
    VerifiedUser,
)
from app.auth.utils import hash_password_async, verify_password_async
from app.config import AuthTokensConfig
from app.service import UnitOfWork
from app.users.errors import UserNotFoundError
from app.users.models import User
from app.common.utils import utcnow


class AuthTokensService:
    def __init__(self, config: AuthTokensConfig) -> None:
        self.config = config

    # read

    @traced("auth.tokens.decode_access_token")
    def decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                jwt=token,
                key=self.config.public_key,
                algorithms=[self.config.algorithm],
            )
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError() from e
        
        if payload.get("type") != "access":
            raise InvalidTokenTypeError()
        
        return payload

    def hash_refresh_token(self, refresh_token: str) -> str:
        return hmac.new(
            self.config.refresh_pepper_bytes, refresh_token.encode(), hashlib.sha256
        ).hexdigest()

    # write

    @traced("auth.tokens.create_access_token")
    def create_access_token(self, user_uuid: UUID) -> str:
        now = utcnow()
        payload: dict[str, Any] = {
            "sub": str(user_uuid),
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(
                (
                    now + timedelta(minutes=self.config.access_token_expire_minutes)
                ).timestamp()
            ),
            "jti": secrets.token_hex(16),
        }

        return jwt.encode(
            payload=payload,
            key=self.config.private_key,
            algorithm=self.config.algorithm,
        )

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(64)

    def issue_tokens(self, user_uuid: UUID) -> IssuedTokens:
        access_token = self.create_access_token(user_uuid=user_uuid)
        refresh_token = self.generate_refresh_token()
        refresh_token_hash = self.hash_refresh_token(refresh_token=refresh_token)

        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_token_hash=refresh_token_hash,
        )
    

class AuthService:
    def __init__(
            self, 
            uow_factory: Callable[[], UnitOfWork], 
            auth_tokens_service: AuthTokensService
        ):
        self.uow_factory = uow_factory
        self.auth_tokens_service = auth_tokens_service

    # helpers

    @staticmethod
    def _to_verified_user(user: User | None) -> VerifiedUser | None:
        if user is None:
            return None

        return VerifiedUser(
            id=user.id,
            uuid=user.uuid,
            hashed_password=user.hashed_password,
        )

    @traced("auth.service.authenticate_user")
    async def _authenticate_user(
            self,
            username: str,
            password: str,
    ) -> VerifiedUser:
        # Argon2 runs after this transaction is closed: no lock, no connection.
        async with self.uow_factory() as uow:
            verified = self._to_verified_user(
                await uow.user_repo.get_by_username(username=username)
            )

        if verified is None or not await verify_password_async(
            password, verified.hashed_password,
        ):
            raise InvalidLoginCredentials("Invalid username or password")

        return verified

    async def _lock_user_with_same_password(
            self,
            verified: VerifiedUser,
            uow: UnitOfWork,
    ) -> User | None:
        # The password could change or the user could be deleted while Argon2 ran.
        user = await uow.user_repo.get_by_id(user_id=verified.id, for_update=True)
        if user is None or user.hashed_password != verified.hashed_password:
            return None

        return user

    async def _get_user_by_refresh_token_hash(
        self, refresh_token_hash: str, uow: UnitOfWork
    ) -> User:
        user_id = await uow.auth_repo.get_user_id_by_refresh(refresh_token_hash)
        if user_id is None:
            raise InvalidRefreshTokenError("Session expired")

        user = await uow.user_repo.get_by_id(user_id=user_id, for_update=True)
        if user is None:
            raise UserNotFoundError()

        return user

    async def _validate_refresh_session(
        self, refresh_token_hash: str, uow: UnitOfWork
    ) -> UserSession:
        user_session = await uow.auth_repo.get_user_session_by_refresh(
            refresh_token_hash, 
            for_update=True,
        )

        if (
            user_session is None
            or user_session.revoked_at is not None
            or user_session.replaced_by_session_id is not None
            or user_session.expires_at <= utcnow()
        ):
            raise InvalidRefreshTokenError("Session expired")

        return user_session

    # read

    @traced("auth.service.get_all_user_sessions")
    async def get_all_user_sessions(self, user_id: int) -> list[UserSession]:
        async with self.uow_factory() as uow:
            return await uow.auth_repo.get_all_user_sessions(user_id)

    # write

    async def build_user_session(
            self,
            user: User,
            refresh_token_hash,
    ) -> UserSession:
        user_session = UserSession(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            expires_at=utcnow() + timedelta(
                days=self.auth_tokens_service.config.refresh_token_expire_days
            ),
        )
        return user_session

    @traced("auth.service.login")
    async def login(
        self,
        username: str,
        password: str,
    ) -> TokenPair:
        verified = await self._authenticate_user(
            username=username,
            password=password,
        )
        async with self.uow_factory() as uow:
            user = await self._lock_user_with_same_password(verified, uow)
            if user is None:
                raise InvalidLoginCredentials("Invalid username or password")

            tokens = self.auth_tokens_service.issue_tokens(user_uuid=user.uuid)
            user_session = await self.build_user_session(
                user, tokens.refresh_token_hash,
            )
            uow.auth_repo.add(user_session=user_session)
            await uow.commit()

            return TokenPair(tokens.access_token, tokens.refresh_token)

    @traced("auth.service.login_by_bearer_token_without_refresh")
    async def login_by_bearer_token_without_refresh(self, username: str, password: str) -> AccessTokenResponse:
        verified = await self._authenticate_user(username, password)
        bearer_access_token = self.auth_tokens_service.create_access_token(verified.uuid)
        return AccessTokenResponse(bearer_access_token)

    @traced("auth.service.refresh")
    async def refresh(
        self,
        refresh_token: str,
    ) -> TokenPair:
        async with self.uow_factory() as uow:
            refresh_token_hash = self.auth_tokens_service.hash_refresh_token(refresh_token)
            user = await self._get_user_by_refresh_token_hash(refresh_token_hash, uow)
            user_session = await self._validate_refresh_session(refresh_token_hash, uow)
            tokens = self.auth_tokens_service.issue_tokens(user.uuid)
            new_user_session = await self.build_user_session(
                user, tokens.refresh_token_hash,
            )
            uow.auth_repo.add(new_user_session)
            await uow.auth_repo.flush()
            user_session.replaced_by_session_id = new_user_session.id
            user_session.revoked_at = utcnow()

            await uow.commit()

            return TokenPair(tokens.access_token, tokens.refresh_token)

    @traced("auth.service.change_password")
    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> None:
        async with self.uow_factory() as uow:
            verified = self._to_verified_user(
                await uow.user_repo.get_by_id(user_id=user_id)
            )

        if verified is None:
            raise InvalidLoginCredentials()

        if not await verify_password_async(
            password=current_password,
            password_hash=verified.hashed_password,
        ):
            raise InvalidLoginCredentials()

        new_password_hash = await hash_password_async(
            password=new_password,
        )

        async with self.uow_factory() as uow:
            user = await self._lock_user_with_same_password(verified, uow)
            if user is None:
                raise InvalidLoginCredentials()

            user.hashed_password = new_password_hash

            await uow.auth_repo.revoke_all_active_sessions_by_user_id(
                user_id=user_id,
                revoked_at=utcnow(),
            )

            await uow.commit()

    @traced("auth.service.logout")
    async def logout(
        self,
        refresh_token: str | None = None,
    ) -> None:
        if not refresh_token:
            return
        async with self.uow_factory() as uow:
            refresh_token_hash = self.auth_tokens_service.hash_refresh_token(refresh_token)
            try:
                await self._get_user_by_refresh_token_hash(refresh_token_hash, uow)
            except (InvalidRefreshTokenError, UserNotFoundError):
                return

            is_updated = await uow.auth_repo.revoke_active_session_by_refresh_token_hash(
                refresh_token_hash=refresh_token_hash,
                revoked_at=utcnow(),
            )
            if is_updated:
                await uow.commit()
