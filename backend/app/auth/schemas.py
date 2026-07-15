from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

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


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: UUID
    user_id: int
    user_agent: str | None
    ip: str | None
    revoked_at: datetime | None
    replaced_by_session_id: int | None