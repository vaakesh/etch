from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    username: str
    email: EmailStr
    hashed_password: str
    created_at: datetime
    updated_at: datetime

class UserCreate(BaseModel):
    username: str = Field(min_lenght=3, max_length=18)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None

class UserOut(UserSchema):
    pass