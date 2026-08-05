from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

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
        max_length=150,
    ),
]

type SearchQuery = Annotated[
    NormalizedSearch | None,
    Query(alias="q"),
]


# SCHEMAS

class PublicUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    username: str
    created_at: datetime

class UserSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locale: str
    theme: str

class PrivateUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    username: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime
    user_settings: UserSettingsOut

class UserCreate(BaseModel):
    username: Username
    email: NormalizedEmail
    password: Password

class UserUpdate(BaseModel):
    username: Username | None = None
    email: NormalizedEmail | None = None

class ChangePassword(BaseModel):
    current_password: Password
    new_password: Password

type Theme = Annotated[
    Literal["light", "dark", "system"],
    Field(description="UI theme"),
]

type Locale = Annotated[
    Literal[
        "ru-RU",
        "en-US",
    ],
    Field(description="User locale in BCP 47 format"),
]

class UserSettingsUpdate(BaseModel):
    locale: Locale
    theme: Theme