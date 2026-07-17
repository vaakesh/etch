from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeckSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    uuid: UUID | None = None
    user_id: int | None = None

    title: str = Field(..., max_length=150)
    description: str | None = None
    words_count: int
    is_public: bool = False

    created_at: datetime | None = None
    updated_at: datetime | None = None

class DeckCreate(BaseModel):
    
    title: str = Field(..., max_length=150)
    description: str | None = None
    is_public: bool = False


class DeckUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=150)
    description: str | None = None
    is_public: bool | None = None


class DeckOut(DeckSchema):
    pass



class DeckCardSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    uuid: UUID | None = None

    deck_id: int
    card_id: int

    position: int = 0

    created_at: datetime | None = None
    updated_at: datetime | None = None

class DeckCardCreate(BaseModel):
    deck_id: int
    card_id: int
    position: int = Field(default=0, ge=0)


class DeckCardUpdate(BaseModel):
    position: int | None = Field(default=None, ge=0)


class DeckCardAdd(BaseModel):
    position: int = Field(default=0, ge=0)


class DeckCardOut(DeckCardSchema):
    pass


class UserDeck(BaseModel):
    user_id: int
    deck_id: int

    sessions_count: int
    correct_count: int
    wrong_count: int
    last_studied_at: datetime
