from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CardSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    user_id: int

    front_text: str = Field(..., max_length=255)
    back_text: str = Field(..., max_length=255)

    source_lang: str = Field(default="ru", max_length=10)
    target_lang: str = Field(default="en", max_length=10)

    created_at: datetime
    updated_at: datetime

class CardCreate(BaseModel):
    user_id: int

    front_text: str = Field(..., max_length=255)
    back_text: str = Field(..., max_length=255)

    source_lang: str = Field(default="ru", max_length=10)
    target_lang: str = Field(default="en", max_length=10)


class CardUpdate(BaseModel):
    front_text: str | None = Field(default=None, max_length=255)
    back_text: str | None = Field(default=None, max_length=255)

    source_lang: str | None = Field(default=None, max_length=10)
    target_lang: str | None = Field(default=None, max_length=10)


class CardOut(CardSchema):
    pass