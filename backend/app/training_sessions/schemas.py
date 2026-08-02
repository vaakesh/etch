from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from app.errors import RequestValueError
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrainingSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID

    requested_count: int
    actual_count: int

    correct_count: int
    wrong_count: int

    prompt_side: str
    answer_side: str

    started_at: datetime
    finished_at: datetime | None

class TrainingSessionStatus(StrEnum):
    FINISHED = "finished"
    UNFINISHED = "unfinished"

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

class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    answer_text: str
    answered_count: int
    correct_count: int
    total_count: int
    is_finished: bool
    time_to_complete: int | None 