from uuid import UUID

from app.common.types import Password, Username
from app.users.types import Locale, NormalizedEmail, Theme
from pydantic import BaseModel, ConfigDict, PastDatetime


class InternalUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    username: Username
    email: NormalizedEmail
    hashed_password: str
    created_at: PastDatetime
    updated_at: PastDatetime

class PublicUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    username: Username
    created_at: PastDatetime

class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locale: Locale
    theme: Theme
    show_previews_for_long: bool

class PrivateUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    username: Username
    email: NormalizedEmail
    created_at: PastDatetime
    updated_at: PastDatetime
    settings: UserSettingsResponse

class CreateUserRequest(BaseModel):
    username: Username
    email: NormalizedEmail
    password: Password

class UpdateUserRequest(BaseModel):
    username: Username | None = None
    email: NormalizedEmail | None = None

class ChangePasswordRequest(BaseModel):
    current_password: Password
    new_password: Password

class UserSettingsUpdate(BaseModel):
    locale: Locale | None = None
    theme: Theme | None = None
    show_previews_for_long: bool | None = None
