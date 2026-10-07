from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.common.types import (
    Counter,
    DeckDescription,
    DeckPosition,
    DeckSize,
    DeckTitle,
    Percent,
    PositiveInt,
    Username,
)
from app.decks.models import Deck
from app.errors import RequestValueError
from pydantic import UUID7, BaseModel, ConfigDict, PastDatetime, StrictBool, ValidationInfo, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.decks.utils import calculate_accuracy

@dataclass(frozen=True, slots=True, kw_only=True)
class DeckLoad:
    user: bool = False
    card_links: bool = False
    cards: bool = False # cards include card_links

@dataclass
class ArchiveCleanupBatch:
    decks: list[tuple[int, UUID]] = field(default_factory=list)
    cards: list[tuple[int, UUID]] = field(default_factory=list)
    user_deck_keys: list[tuple[int, int]] = field(default_factory=list)

class DeckTimestamps(BaseModel):
    created_at: PastDatetime
    updated_at: PastDatetime

    @field_validator("updated_at")
    @classmethod
    def validate_dates_order(cls, value: datetime, info: ValidationInfo) -> datetime:
        created_at = info.data.get("created_at")
        if created_at is not None:
            try:
                valid_order = value >= created_at
            except TypeError:
                raise RequestValueError(
                    message="Dates must have compatible timezone information",
                    failed_field="updated_at",
                ) from None
            if not valid_order:
                raise RequestValueError(
                    message="updated_at must be greater than or equal to created_at",
                    failed_field="updated_at",
                )
        return value

class InternalDeck(DeckTimestamps):
    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    uuid: UUID7
    user_id: PositiveInt
    owner_uuid: UUID7
    owner_username: Username
    title: DeckTitle
    description: DeckDescription
    words_count: DeckSize
    is_public: StrictBool
    saves_count: Counter
    version: PositiveInt

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

    user_id: PositiveInt
    deck_id: PositiveInt
    sessions_count: Counter
    correct_count: Counter
    wrong_count: Counter
    last_studied_at: PastDatetime | None
    is_favourite: StrictBool
    is_saved: StrictBool
    last_seen_version: PositiveInt | None
    added_at: PastDatetime

    @model_validator(mode="after")
    def validate_study_state(self) -> InternalUserDeck:
        if self.sessions_count == 0:
            for field in ("correct_count", "wrong_count"):
                if getattr(self, field) != 0:
                    raise RequestValueError(
                        message=f"{field} must be zero without completed sessions",
                        failed_field=field,
                    )

        if (self.sessions_count == 0) != (self.last_studied_at is None):
            raise RequestValueError(
                message="last_studied_at must be set exactly when completed sessions exist",
                failed_field="last_studied_at",
            )

        if self.last_studied_at is not None:
            try:
                valid_order = self.last_studied_at >= self.added_at
            except TypeError:
                raise RequestValueError(
                    message="Dates must have compatible timezone information",
                    failed_field="last_studied_at",
                ) from None
            if not valid_order:
                raise RequestValueError(
                    message="last_studied_at must be greater than or equal to added_at",
                    failed_field="last_studied_at",
                )
        return self

class InternalDeckCard(DeckTimestamps):
    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    uuid: UUID7
    deck_id: PositiveInt
    card_id: PositiveInt
    position: DeckPosition

class DeckCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    uuid: UUID7
    position: DeckPosition

class CreateDeckRequest(BaseModel):
    title: DeckTitle
    description: DeckDescription = None
    is_public: StrictBool = False

class UpdateDeckRequest(BaseModel):
    title: DeckTitle | SkipJsonSchema[None] = None
    description: DeckDescription = None
    is_public: StrictBool | SkipJsonSchema[None] = None

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

    uuid: UUID7
    owner_uuid: UUID7
    owner_username: Username
    title: DeckTitle
    description: DeckDescription = None
    words_count: DeckSize
    is_public: StrictBool
    saves_count: Counter
    updated_at: PastDatetime


class PreserveArchivedDeckResponse(BaseModel):
    uuid: UUID7
    already_preserved: bool
    copy_deleted: bool


class ArchiveOfferResponse(BaseModel):
    uuid: UUID7
    title: DeckTitle
    expires_at: datetime
    preserved_deck_uuid: UUID7 | None


class ArchivedDeckResponse(BaseModel):
    uuid: UUID7
    title: DeckTitle
    description: DeckDescription = None
    words_count: DeckSize
    archived_at: datetime
    expires_at: datetime
    archive_reason: str
    source_deck_uuid_snapshot: UUID7 | None
    preserved_deck_uuid: UUID7 | None

class DeckListItemResponse(BaseModel):
    deck: DeckResponse
    viewer_state: DeckViewerStateResponse

class DeckViewerStateResponse(BaseModel):
    sessions_count: Counter
    correct_count: Counter
    wrong_count: Counter
    accuracy: Percent
    last_studied_at: PastDatetime | None
    is_favourite: StrictBool
    is_saved: StrictBool

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
    card_uuid: UUID7
    to_position: DeckPosition

class LibraryCursor(BaseModel):
    last_studied_at: PastDatetime | None
    added_at: PastDatetime
    id: PositiveInt
