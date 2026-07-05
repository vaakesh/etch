from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    user_id: int
    deck_id: int

    requested_count: int = Field(..., ge=0)
    actual_count: int = Field(..., ge=0)

    correct_count: int = Field(default=0, ge=0)
    wrong_count: int = Field(default=0, ge=0)
    score: int = Field(default=0, ge=0)

    prompt_side: str = Field(default="front", max_length=20)
    answer_side: str = Field(default="back", max_length=20)


class TrainingSessionUpdate(BaseModel):
    requested_count: int | None = Field(default=None, ge=0)
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