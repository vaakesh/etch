


import hashlib
import hmac
import secrets
from collections.abc import Callable
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
from app.auth.schemas import AccessTokenResponse, IssuedTokens, TokenPair
from app.auth.utils import hash_password, verify_password
from app.config import AuthTokensConfig
from app.service import UnitOfWork
from app.users.errors import UserNotFoundError
from app.users.models import User
from app.common.utils import utcnow


class AuthTokensService:
    def __init__(self, config: AuthTokensConfig) -> None:
        self.config = config

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
    
    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(64)
    
    def hash_refresh_token(self, refresh_token: str) -> str:
        return hmac.new(
            self.config.refresh_pepper_bytes, refresh_token.encode(), hashlib.sha256
        ).hexdigest()
    
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

    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> None:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_id(
                user_id=user_id,
                for_update=True,
            )

            if user is None:
                raise InvalidLoginCredentials()

            if not verify_password(
                password=current_password,
                password_hash=user.hashed_password,
            ):
                raise InvalidLoginCredentials()

            user.hashed_password = hash_password(
                password=new_password,
            )

            await uow.auth_repo.revoke_all_active_sessions_by_user_id(
                user_id=user_id,
                revoked_at=utcnow(),
            )

            await uow.commit()

    async def login(
        self,
        username: str,
        password: str,
    ) -> TokenPair:
        async with self.uow_factory() as uow:
            user = await self._authenticate_user(
                username=username,
                password=password,
                uow=uow,
            )
            tokens = self.auth_tokens_service.issue_tokens(user_uuid=user.uuid)
            user_session = await self.build_user_session(
                user, tokens.refresh_token_hash,
            )
            uow.auth_repo.add(user_session=user_session)
            await uow.commit()

            return TokenPair(tokens.access_token, tokens.refresh_token)

    async def login_by_bearer_token_without_refresh(self, username: str, password: str) -> AccessTokenResponse:
        async with self.uow_factory() as uow:
            user = await self._authenticate_user(
                username,
                password,
                uow,
            )
            bearer_access_token = self.auth_tokens_service.create_access_token(user.uuid)
            return AccessTokenResponse(bearer_access_token)
        
    async def logout(
        self,
        refresh_token: str | None = None,
    ) -> None:
        if not refresh_token:
            return
        revoked_at = utcnow()
        async with self.uow_factory() as uow:
            refresh_token_hash = self.auth_tokens_service.hash_refresh_token(refresh_token)
            is_updated = await uow.auth_repo.revoke_active_session_by_refresh_token_hash(
                refresh_token_hash=refresh_token_hash,
                revoked_at=revoked_at,
            )
            if is_updated:
                await uow.commit()
    
    async def refresh(
        self,
        refresh_token: str,
    ) -> TokenPair:
        async with self.uow_factory() as uow:
            user_session = await self._validate_refresh_token(refresh_token, uow)
            user = await uow.user_repo.get_by_id(user_session.user_id)
            if user is None:
                raise UserNotFoundError()
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

    async def _validate_refresh_token(
        self, refresh_token: str, uow: UnitOfWork
    ) -> UserSession:
        refresh_token_hash = self.auth_tokens_service.hash_refresh_token(refresh_token)
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


    async def _authenticate_user(
            self,
            username: str,
            password: str,
            uow: UnitOfWork,
    ) -> User:
        user = await uow.user_repo.get_by_username(username=username)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidLoginCredentials("Invalid username or password")
        
        return user
    
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
    
    async def get_all_user_sessions(self, user_id: int) -> list[UserSession]:
        async with self.uow_factory() as uow:
            return await uow.auth_repo.get_all_user_sessions(user_id)
