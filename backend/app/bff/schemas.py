





from datetime import date as Date
from uuid import UUID

from app.cards.schemas import CardResponse
from pydantic import BaseModel, ConfigDict, PastDatetime

from app.decks.schemas import DeckResponse, DeckTitle, DeckDescription, DeckViewerStateResponse
from app.training_sessions.schemas import Counter, Percent, Seconds


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
    percent: Percent

class HomeDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decks: list[HomeDeckItemResponse]
    progress: UserProgressResponse
    user_weekly_activity: list[DailyActivityResponse]

class LibraryDeckItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck: DeckResponse
    viewer_state: DeckViewerStateResponse
    preview_cards: list[CardResponse]

class LibraryCardItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card: CardResponse