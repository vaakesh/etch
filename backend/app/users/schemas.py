from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints

from app.users.types import Locale, Theme

# TYPES

type Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=18,
        pattern=r"^\S+$",
    ),
    
]

type Password = Annotated[
    str,
    StringConstraints(
        min_length=8,
        max_length=128,
        pattern=r"^\S+$",
    ),
]

type NormalizedEmail = Annotated[
    EmailStr,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
    )
]

type NormalizedSearch = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=50,
    ),
]

type SearchQuery = Annotated[
    NormalizedSearch | None,
    Query(alias="q"),
]


# SCHEMAS

class PublicUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    username: str
    created_at: datetime

class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locale: str
    theme: str
    show_previews_for_long: bool

class PrivateUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    username: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime
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
