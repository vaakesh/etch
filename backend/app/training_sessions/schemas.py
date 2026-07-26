from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrainingSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    uuid: UUID | None = None

    user_id: int | None = None
    deck_id: int

    requested_count: int = Field(..., ge=0)
    actual_count: int = Field(..., ge=0)

    correct_count: int = Field(default=0, ge=0)
    wrong_count: int = Field(default=0, ge=0)
    score: int = Field(default=0, ge=0)

    prompt_side: str = Field(default="front", max_length=20)
    answer_side: str = Field(default="back", max_length=20)

    started_at: datetime | None = None
    finished_at: datetime | None = None

class TrainingSessionCreate(BaseModel):
    deck_id: int

    requested_count: int = Field(..., ge=0)

    prompt_side: str = Field(default="front", max_length=20)
    answer_side: str = Field(default="back", max_length=20)


class TrainingSessionUpdate(BaseModel):
    actual_count: int | None = Field(default=None, ge=0)

    correct_count: int | None = Field(default=None, ge=0)
    wrong_count: int | None = Field(default=None, ge=0)
    score: int | None = Field(default=None, ge=0)

    prompt_side: str | None = Field(default=None, max_length=20)
    answer_side: str | None = Field(default=None, max_length=20)

    finished_at: datetime | None = None


class TrainingSessionFinish(BaseModel):
    correct_count: int = Field(..., ge=0)
    wrong_count: int = Field(..., ge=0)
    score: int = Field(..., ge=0)


class TrainingSessionOut(TrainingSessionSchema):
    pass

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
            raise RequestValidationError("Answer must not be empty")
        return value


UserAnswer = Annotated[
    SkipAnswer | SubmittedAnswer,
    Field(discriminator="action"),
]

class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    answer_text: str
    answered_count: int
    correct_count: int
    total_count: int
    is_finished: bool
    time_to_complete: int | None 