from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.common.types import (
    Counter,
    DeckDescription,
    DeckSize,
    DeckTitle,
    Percent,
    PositiveInt,
    Username,
)
from app.decks.models import Deck
from app.errors import RequestValueError
from pydantic import BaseModel, ConfigDict, PastDatetime, model_validator

from app.decks.utils import calculate_accuracy

@dataclass(frozen=True, slots=True, kw_only=True)
class DeckLoad:
    user: bool = False
    card_links: bool = False
    cards: bool = False # cards include card_links

class InternalDeck(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    user_id: int
    owner_uuid: UUID
    owner_username: Username
    title: DeckTitle
    description: DeckDescription
    words_count: DeckSize
    is_public: bool
    saves_count: Counter
    version: PositiveInt
    created_at: PastDatetime
    updated_at: PastDatetime

    @classmethod
    def from_entity(cls, deck: Deck) -> InternalDeck:
        return cls(
            id=deck.id,
            uuid=deck.uuid,
            user_id=deck.user_id,
            owner_uuid=deck.owner_uuid,
            owner_username=deck.owner_username,
            title=deck.title,
            description=deck.description,
            words_count=deck.words_count,
            is_public=deck.is_public,
            saves_count=deck.saves_count,
            version=deck.version,
            created_at=deck.created_at,
            updated_at=deck.updated_at,
        )

class InternalUserDeck(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    deck_id: int
    sessions_count: Counter
    correct_count: Counter
    wrong_count: Counter
    last_studied_at: PastDatetime | None
    is_favourite: bool
    is_saved: bool
    last_seen_version: PositiveInt | None
    added_at: PastDatetime

class InternalDeckCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    deck_id: int
    card_id: int
    position: PositiveInt
    created_at: PastDatetime
    updated_at: PastDatetime

class DeckCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: UUID
    position: PositiveInt

class CreateDeckRequest(BaseModel):
    title: DeckTitle
    description: DeckDescription = None
    is_public: bool = False

class UpdateDeckRequest(BaseModel):
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

class DeckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    owner_uuid: UUID
    owner_username: Username
    title: DeckTitle
    description: DeckDescription = None
    words_count: DeckSize
    is_public: bool
    saves_count: Counter
    updated_at: PastDatetime | None = None

class DeckListItemResponse(BaseModel):
    deck: DeckResponse
    viewer_state: DeckViewerStateResponse

class DeckViewerStateResponse(BaseModel):
    sessions_count: Counter
    correct_count: Counter
    wrong_count: Counter
    accuracy: Percent
    last_studied_at: PastDatetime | None
    is_favourite: bool
    is_saved: bool

    @classmethod
    def validate(cls, user_deck: InternalUserDeck) -> DeckViewerStateResponse:
        return cls(
            sessions_count=user_deck.sessions_count,
            correct_count=user_deck.correct_count,
            wrong_count=user_deck.wrong_count,
            accuracy=calculate_accuracy(
                user_deck=user_deck
            ),
            last_studied_at=user_deck.last_studied_at,
            is_favourite=user_deck.is_favourite,
            is_saved=user_deck.is_saved,
        )

class ReorderCards(BaseModel):
    card_uuid: UUID
    to_position: PositiveInt

class LibraryCursor(BaseModel):
    last_studied_at: PastDatetime | None
    added_at: PastDatetime
    id: PositiveInt
