from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from app.errors import RequestValueError
from pydantic import BaseModel, ConfigDict, Field, field_validator, PastDatetime

from app.training_sessions.models import CardSide, TrainingSessionStatus
from app.cards.schemas import CardLang, CardText

type Counter = Annotated[
    int,
    Field(ge=0),
]

type Percent = Annotated[
    int,
    Field(ge=0, le=100),
]

class TrainingSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    deck_uuid: UUID

    status: TrainingSessionStatus

    requested_count: Counter
    actual_count: Counter

    correct_count: Counter
    wrong_count: Counter

    prompt_side: CardSide
    answer_side: CardSide

    started_at: PastDatetime
    finished_at: PastDatetime | None

class SkipAnswer(BaseModel):
    action: Literal["skip"]
    answer: None = None

class SubmittedAnswer(BaseModel):
    action: Literal["answer"]
    answer: str

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

type UserAnswer = Annotated[
    SkipAnswer | SubmittedAnswer,
    Field(discriminator="action"),
]

type Seconds = Annotated[
    int,
    Field(ge=0),
]

class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    answer_text: CardText
    answered_count: Counter
    correct_count: Counter
    total_count: Counter
    is_finished: bool
    time_to_complete: Seconds | None 

type PositiveInt = Annotated[
    int,
    Field(ge=1),
]

class TrainingSessionItemOut(BaseModel):
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