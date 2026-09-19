from dataclasses import dataclass
from uuid import UUID

from app.common.types import Password, Username
from pydantic import BaseModel, ConfigDict, PastDatetime


@dataclass(slots=True, frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    refresh_token_hash: str


@dataclass(slots=True, frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(slots=True)
class AccessTokenResponse:
    access_token: str
    token_type: str = "Bearer"


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_agent: str | None
    ip: str | None
    revoked_at: PastDatetime | None

class LoginRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: Username
    password: Password

class ChangePasswordRequest(BaseModel):
    current_password: Password
    new_password: Password
