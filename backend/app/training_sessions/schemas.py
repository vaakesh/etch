from typing import Annotated, Literal
from uuid import UUID

from app.common.types import (
    CardLang,
    CardText,
    Counter,
    DeckTitle,
    PositiveInt,
    Seconds,
    SessionSize,
)
from app.errors import RequestValueError
from app.training_sessions.models import CardSide, TrainingSessionStatus
from pydantic import BaseModel, ConfigDict, Field, PastDatetime, field_validator


class InternalTrainingSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    user_id: int
    deck_uuid: UUID
    deck_title: DeckTitle
    status: TrainingSessionStatus
    requested_count: SessionSize
    actual_count: Counter
    correct_count: Counter
    wrong_count: Counter
    prompt_side: CardSide
    answer_side: CardSide
    started_at: PastDatetime
    finished_at: PastDatetime | None

class InternalTrainingSessionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    training_session_id: int
    sequence_number: PositiveInt
    original_card_uuid: UUID
    user_typed_text: CardText | None
    prompt_text: CardText
    answer_text: CardText
    prompt_lang: CardLang
    answer_lang: CardLang
    is_answered: bool
    is_correct: bool | None
    answered_at: PastDatetime | None

class PracticeCardResponse(BaseModel):
    sequence_number: PositiveInt

    prompt_text: CardText
    prompt_language: CardLang
    answer_language: CardLang

class PracticeSessionResponse(BaseModel):
    training_session_uuid: UUID

    deck_uuid: UUID

    prompt_side: CardSide
    answer_side: CardSide

    total_count: SessionSize
    answered_count: Counter
    correct_count: Counter
    wrong_count: Counter

    started_at: PastDatetime
    cards: list[PracticeCardResponse]

class TrainingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    deck_uuid: UUID
    deck_title: DeckTitle

    status: TrainingSessionStatus

    requested_count: SessionSize
    actual_count: Counter

    correct_count: Counter
    wrong_count: Counter

    prompt_side: CardSide
    answer_side: CardSide

    started_at: PastDatetime
    finished_at: PastDatetime | None

class SkipAnswerRequest(BaseModel):
    action: Literal["skip"]
    answer: None = None

class SubmittedAnswerRequest(BaseModel):
    action: Literal["answer"]
    answer: CardText

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise RequestValueError(
                "Answer must not be empty", 
                failed_field="answer",
            )
        return value

class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    answer_text: CardText
    answered_count: Counter
    correct_count: Counter
    total_count: Counter
    is_finished: bool
    time_to_complete: Seconds | None

class StartPracticeSessionRequest(BaseModel):
    prompt_side: CardSide
    words_per_session: SessionSize

class TrainingSessionHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_uuid: UUID
    sequence_number: PositiveInt
    prompt_text: CardText
    answer_text: CardText
    prompt_lang: CardLang
    answer_lang: CardLang
    user_typed_text: CardText | None

    is_answered: bool
    is_correct: bool | None

class ResumeTrainingSessionActivityRequest(BaseModel):
    event: Literal["resume"]


class ActiveTrainingSessionActivityRequest(BaseModel):
    event: Literal["pause", "heartbeat"]
    tracker_uuid: UUID


type TrainingSessionActivityRequest = Annotated[
    ResumeTrainingSessionActivityRequest
    | ActiveTrainingSessionActivityRequest,
    Field(discriminator="event"),
]

class TrainingSessionActivityResponse(BaseModel):
    tracker_uuid: UUID | None