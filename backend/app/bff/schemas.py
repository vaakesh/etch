





from datetime import date as Date
from uuid import UUID

from app.cards.schemas import CardResponse
from app.common.types import Counter, DeckDescription, DeckTitle, Percent, Seconds
from app.decks.schemas import DeckResponse, DeckViewerStateResponse
from pydantic import BaseModel, ConfigDict, PastDatetime


class HomeDeckItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    owner_uuid: UUID
    title: DeckTitle
    description: DeckDescription = None
    words_count: Counter
    user_accuracy: Percent
    updated_at: PastDatetime | None = None

class UserProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_words_explored: Counter
    user_weekly_accuracy: Percent
    user_current_streak: Counter # days
    user_total_study_time: Seconds # seconds

class DailyActivityResponse(BaseModel):
    date: Date
    value: Counter

class HomeDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decks: list[HomeDeckItemResponse]
    progress: UserProgressResponse
    user_weekly_activity: list[DailyActivityResponse]

class CatalogDeckItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck: DeckResponse
    viewer_state: DeckViewerStateResponse | None

class LibraryDeckItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck: DeckResponse
    viewer_state: DeckViewerStateResponse
    preview_cards: list[CardResponse]

class LibraryCardItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card: CardResponse
