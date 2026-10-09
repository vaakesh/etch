from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.common.types import Password, Username
from pydantic import BaseModel, ConfigDict


@dataclass(slots=True, frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    refresh_token_hash: str


@dataclass(slots=True, frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(slots=True, frozen=True)
class VerifiedUser:
    id: int
    uuid: UUID
    hashed_password: str


@dataclass(slots=True, frozen=True)
class ClientInfo:
    ip: str | None
    user_agent: str | None


@dataclass(slots=True)
class AccessTokenResponse:
    access_token: str
    token_type: str = "Bearer"


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: UUID
    user_agent: str | None
    ip: str | None
    created_at: datetime
    expires_at: datetime

class LoginRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: Username
    password: Password

class ChangePasswordRequest(BaseModel):
    current_password: Password
    new_password: Password

class ChallengeParametersResponse(BaseModel):
    algorithm: str
    cost: int
    keyLength: int
    keyPrefix: str
    nonce: str
    salt: str
    expiresAt: int


class ChallengeResponse(BaseModel):
    parameters: ChallengeParametersResponse
    signature: str