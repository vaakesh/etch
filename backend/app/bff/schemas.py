





from datetime import date as Date
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.cards.schemas import CardLang, CardText
from pydantic import BaseModel, ConfigDict, Field


# home page

# todo: change deckdashboard to decklibrarypage
class DeckDashboard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck_uuid: UUID
    owner_uuid: UUID
    title: str
    description: str | None = None
    deck_words_count: int
    user_accuracy: int
    updated_at: datetime | None = None

class UserProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_words_explored: int
    user_weekly_accuracy: float
    user_current_streak: int # days
    user_total_study_time: int # seconds

class WeeklyActivityDay(BaseModel):
    date: Date
    percent: int = Field(ge=0, le=100)

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
    title: str
    description: str | None = None
    deck_words_count: int
    user_accuracy: int
    is_favourite: bool
    updated_at: datetime | None = None

    cards: list[CardLibraryPage]

class CardLibraryPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    card_uuid: UUID

    front_text: CardText
    back_text: CardText
    source_lang: CardLang
    target_lang: CardLang

    updated_at: datetime

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

