from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.users.schemas import Password, Username
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
class BearerToken:
    access_token: str
    token_type: str = "Bearer"


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: UUID
    user_id: int
    user_agent: str | None
    ip: str | None
    revoked_at: PastDatetime | None
    replaced_by_session_id: int | None

class LoginRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: Username
    password: Password