





from datetime import date as Date
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.cards.schemas import CardLang, CardText
from pydantic import BaseModel, ConfigDict, Field, PastDatetime

from app.decks.schemas import DeckTitle, DeckDescription
from app.training_sessions.schemas import Counter, Percent, Seconds


# home page

# todo: change deckdashboard to decklibrarypage
class DeckDashboard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck_uuid: UUID
    owner_uuid: UUID
    title: DeckTitle
    description: DeckDescription = None
    deck_words_count: Counter
    user_accuracy: Percent
    updated_at: PastDatetime | None = None

class UserProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_words_explored: Counter
    user_weekly_accuracy: Percent
    user_current_streak: Counter # days
    user_total_study_time: Seconds # seconds

class WeeklyActivityDay(BaseModel):
    date: Date
    percent: Percent

class HomeDashboard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decks: list[DeckDashboard]
    progress: UserProgress
    user_weekly_activity: list[WeeklyActivityDay]


# library page
class DeckLibraryPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck_uuid: UUID
    owner_uuid: UUID
    title: DeckTitle
    description: DeckDescription = None
    deck_words_count: Counter
    user_accuracy: Percent
    is_favourite: bool
    updated_at: PastDatetime | None = None

    cards: list[CardLibraryPage]

class CardLibraryPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_uuid: UUID

    front_text: CardText
    back_text: CardText
    front_lang: CardLang
    back_lang: CardLang

    updated_at: PastDatetime

    # decks_contain_count: int



# training session
class CreateTrainingSession(BaseModel):
    prompt_side: Literal["front", "back"]

class PracticeCard(BaseModel):
    sequence_number: int = Field(ge=1)

    prompt_text: str
    prompt_language: str
    answer_language: str

class PracticeSessionResponse(BaseModel):
    training_session_uuid: UUID

    deck_uuid: UUID

    prompt_side: Literal["front", "back"]
    answer_side: Literal["front", "back"]

    total_count: int
    answered_count: int
    correct_count: int
    wrong_count: int

    started_at: datetime
    cards: list[PracticeCard]

