from dataclasses import dataclass
from datetime import datetime
from typing import Hashable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PastDatetime

from app.cards.models import Card
from app.cards.schemas import CardLang, CardText
from app.decks.models import Deck
from app.training_sessions.schemas import Counter, PositiveInt
from app.decks.schemas import DeckDescription, DeckTitle

type UserDeckIdentity = tuple[int, int]

@dataclass(slots=True)
class CacheLookupResult[K: Hashable, T]:
    cached: dict[K, T]
    missing: list[K]

class CachedLibraryPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_uuids: list[UUID]
    next_cursor: str | None
    has_more: bool

@dataclass(frozen=True, slots=True)
class LibraryPageCacheLookup:
    page: CachedLibraryPage | None
    generation: int | None

class CachedUserDeck(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    deck_id: int
    sessions_count: Counter
    correct_count: Counter
    wrong_count: Counter
    last_studied_at: PastDatetime | None
    is_favourite: bool
    is_following: bool
    last_seen_version: int | None
    added_at: PastDatetime

class CachedCard(BaseModel):
    id: int
    uuid: UUID
    front_text: CardText
    back_text: CardText
    front_lang: CardLang
    back_lang: CardLang
    created_at: PastDatetime
    updated_at: PastDatetime

    @classmethod
    def from_entity(cls, card: Card) -> CachedCard:
        return cls(
            id=card.id,
            uuid=card.uuid,
            front_text=card.front_text,
            back_text=card.back_text,
            front_lang=card.front_lang,
            back_lang=card.back_lang,
            created_at=card.created_at,
            updated_at=card.updated_at,
        )

class CachedDeck(BaseModel):
    id: int
    uuid: UUID
    owner_uuid: UUID
    title: DeckTitle
    description: DeckDescription
    words_count: Counter
    is_public: bool
    version: PositiveInt
    created_at: PastDatetime
    updated_at: PastDatetime

    @classmethod
    def from_entity(cls, deck: Deck) -> "CachedDeck":
        return cls(
            id=deck.id,
            uuid=deck.uuid,
            owner_uuid=deck.owner_uuid,
            title=deck.title,
            description=deck.description,
            words_count=deck.words_count,
            is_public=deck.is_public,
            version=deck.version,
            created_at=deck.created_at,
            updated_at=deck.updated_at,
        )
