from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PastDatetime

from app.cards.models import Card
from app.cards.schemas import CardLang, CardText
from app.decks.models import Deck
from app.training_sessions.schemas import Counter, PositiveInt
from app.decks.schemas import DeckDescription, DeckTitle


@dataclass(slots=True)
class CacheLookupResult[T]:
    cached: dict[UUID, T]
    missing: list[UUID]

class CachedLibraryPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    deck_uuids: list[UUID]
    next_cursor: str | None
    has_more: bool

@dataclass(frozen=True, slots=True)
class LibraryPageCacheLookup:
    page: CachedLibraryPage | None
    generation: int | None

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
