





from datetime import date as Date
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.cards.schemas import CardOut
from app.decks.schemas import DeckWithUserData, DeckWithUserDataInternal


class DeckDashboard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str | None = None
    deck_total_words_count: int
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

class DeckForDeckPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    title: str
    description: str | None = None
    deck_total_words_count: int
    user_accuracy: int
    is_favourite: bool
    updated_at: datetime | None = None

    cards: list[CardOut]

    

class DeckPageData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decks: list[DeckForDeckPage]
    next_cursor: str | None
    has_more: bool

class DeckPageFavouritesDecks(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decks: list[DeckWithUserData]
    next_cursor: str | None
    has_more: bool


class CardsLibraryPage(BaseModel):

    card_uuid: UUID
    card_owner_uuid: UUID

    card_front_text: str
    card_back_text: str
    card_source_lang: str
    card_target_lang: str

    card_updated_at: datetime

class ResponseCardsLibraryPage(BaseModel):
    
    cards: list[CardsLibraryPage]
    cursor: str | None
    has_more: bool

class CardPracticeSession(BaseModel):

    card_uuid: UUID

    card_front_text: str
    card_back_text: str
    card_source_lang: str
    card_target_lang: str


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

