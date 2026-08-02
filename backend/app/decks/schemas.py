from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from app.cards.schemas import CardDetail
from app.errors import RequestValueError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

type DeckTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=50,
    ),
]

type DeckDescription = (
    Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            max_length=3000,
        ),
    ]
    | None
)

class DeckCreate(BaseModel):
    title: DeckTitle
    description: DeckDescription = None
    is_public: bool = False


class DeckUpdate(BaseModel):
    title: DeckTitle | None = None
    description: DeckDescription = None
    is_public: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_not_nullable_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in ("title", "is_public"):
                if field in data and data[field] is None:
                    raise RequestValueError(
                        message=f"{field} value cannot be null",
                        failed_field=field,
                    )

        return data


class DeckDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    # owner_uuid: UUID | None = Field(
    #     default=None,
    #     validation_alias="__external_owner_uuid",
    # )

    title: str
    description: str | None = None
    words_count: int
    is_public: bool = False

    updated_at: datetime | None = None

class DeckCompact(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    title: str
    words_count: int

class DeckSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    title: str
    description: str | None = None
    words_count: int


class DeckWithUserState(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck: DeckSummary
    user_deck: UserDeckDetails


class UserDeckDetails(BaseModel):
    sessions_count: int
    correct_count: int
    wrong_count: int
    last_studied_at: datetime | None
    is_favourite: bool
    is_following: bool


class DeckCardDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck_uuid: UUID
    card_uuid: UUID

    position: int


class ReorderCards(BaseModel):
    card_uuid: UUID
    to_position: int = Field(ge=1)


class CursorPage[T](BaseModel):

    items: list[T]
    next_cursor: str | None
    has_more: bool