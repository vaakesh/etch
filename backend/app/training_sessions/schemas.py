from typing import Annotated, Literal, Self

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
from pydantic import BaseModel, ConfigDict, Field, PastDatetime, StrictBool, UUID7, field_validator, model_validator


class TrainingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID7
    deck_uuid: UUID7 | None
    deck_title: DeckTitle | None
    status: TrainingSessionStatus
    requested_count: SessionSize
    answered_count: Counter
    correct_count: Counter
    wrong_count: Counter
    prompt_side: CardSide
    answer_side: CardSide
    started_at: PastDatetime
    finished_at: PastDatetime | None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.answered_count > self.requested_count:
            raise RequestValueError("answered_count must not exceed requested_count", failed_field="answered_count")
        if self.correct_count + self.wrong_count != self.answered_count:
            raise RequestValueError("Answer counts must sum to answered_count", failed_field="answered_count")
        if self.prompt_side == self.answer_side:
            raise RequestValueError("Card sides must differ", failed_field="answer_side")
        if (self.status == TrainingSessionStatus.IN_PROGRESS) != (self.finished_at is None):
            raise RequestValueError("finished_at must match session status", failed_field="finished_at")
        if self.status == TrainingSessionStatus.COMPLETED and self.answered_count != self.requested_count:
            raise RequestValueError("Completed sessions must have all cards answered", failed_field="answered_count")
        if self.finished_at is not None:
            try:
                valid = self.finished_at >= self.started_at
            except TypeError:
                raise RequestValueError("Timestamps have incompatible timezone information", failed_field="finished_at") from None
            if not valid:
                raise RequestValueError("finished_at must not precede started_at", failed_field="finished_at")
        return self


class InternalTrainingSession(TrainingSessionResponse):
    id: PositiveInt
    user_id: PositiveInt
    deck_id: PositiveInt | None
    active_study_time_ms: Counter
    activity_tracker_uuid: UUID7 | None
    activity_last_seen_at: PastDatetime | None

    @model_validator(mode="after")
    def validate_activity(self) -> Self:
        if (self.activity_tracker_uuid is None) != (self.activity_last_seen_at is None):
            raise RequestValueError("Activity tracker and timestamp must be set together", failed_field="activity_tracker_uuid")
        if self.activity_last_seen_at is not None:
            if self.status != TrainingSessionStatus.IN_PROGRESS:
                raise RequestValueError("Finished sessions cannot track activity", failed_field="activity_tracker_uuid")
            try:
                valid = self.activity_last_seen_at >= self.started_at
            except TypeError:
                raise RequestValueError("Timestamps have incompatible timezone information", failed_field="activity_last_seen_at") from None
            if not valid:
                raise RequestValueError("Activity must not precede started_at", failed_field="activity_last_seen_at")
        return self

class InternalTrainingSessionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    uuid: UUID7
    training_session_id: PositiveInt
    sequence_number: SessionSize
    original_card_id: PositiveInt | None
    user_typed_text: CardText | None
    prompt_text: CardText
    answer_text: CardText
    prompt_lang: CardLang
    answer_lang: CardLang
    is_answered: StrictBool
    is_correct: StrictBool | None
    answered_at: PastDatetime | None

    @model_validator(mode="after")
    def validate_answer_state(self) -> Self:
        if self.is_answered != (self.is_correct is not None):
            raise RequestValueError("is_correct must match answer state", failed_field="is_correct")
        if self.is_answered != (self.answered_at is not None):
            raise RequestValueError("answered_at must match answer state", failed_field="answered_at")
        if not self.is_answered and self.user_typed_text is not None:
            raise RequestValueError("Unanswered cards cannot contain an answer", failed_field="user_typed_text")
        if self.is_correct and self.user_typed_text is None:
            raise RequestValueError("A skipped card cannot be correct", failed_field="is_correct")
        return self

class PracticeCardResponse(BaseModel):
    sequence_number: SessionSize

    prompt_text: CardText
    prompt_language: CardLang
    answer_language: CardLang

class PracticeSessionResponse(BaseModel):
    training_session_uuid: UUID7

    deck_uuid: UUID7 | None

    prompt_side: CardSide
    answer_side: CardSide

    total_count: SessionSize
    answered_count: Counter
    correct_count: Counter
    wrong_count: Counter

    started_at: PastDatetime
    cards: list[PracticeCardResponse]

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
    is_correct: StrictBool
    answer_text: CardText
    answered_count: Counter
    correct_count: Counter
    total_count: Counter
    is_finished: StrictBool
    time_to_complete: Seconds | None

class StartPracticeSessionRequest(BaseModel):
    prompt_side: CardSide
    words_per_session: SessionSize

class TrainingSessionHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_uuid: UUID7
    sequence_number: SessionSize
    prompt_text: CardText
    answer_text: CardText
    prompt_lang: CardLang
    answer_lang: CardLang
    user_typed_text: CardText | None

    is_answered: StrictBool
    is_correct: StrictBool | None

class ResumeTrainingSessionActivityRequest(BaseModel):
    event: Literal["resume"]


class ActiveTrainingSessionActivityRequest(BaseModel):
    event: Literal["pause", "heartbeat"]
    tracker_uuid: UUID7


type TrainingSessionActivityRequest = Annotated[
    ResumeTrainingSessionActivityRequest
    | ActiveTrainingSessionActivityRequest,
    Field(discriminator="event"),
]

class TrainingSessionActivityResponse(BaseModel):
    tracker_uuid: UUID7 | None
