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
from app.training_sessions.models import CardSide, TrainingSessionKind, TrainingSessionStatus
from app.users.types import Timezone
from pydantic import (
    UUID7,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PastDatetime,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)


class TrainingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID7
    kind: TrainingSessionKind
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

    kind: TrainingSessionKind
    # None у сессии повторения: слова из разных колод
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
    # Когда слово вернётся на повторение по автоматической оценке ответа. None — у ответа
    # нет learning_key или запрос повторный: память с тех пор могла уйти вперёд
    next_review_at: AwareDatetime | None

# 1 = again, 2 = hard, 3 = good, 4 = easy — как Rating в app/fsrs
type SelfRating = Annotated[StrictInt, Field(ge=1, le=4)]

class RateAnswerRequest(BaseModel):
    rating: SelfRating

class RateAnswerResponse(BaseModel):
    rating: SelfRating
    # Когда слово стоит повторить. None — у старого ответа нет learning_key
    next_review_at: AwareDatetime | None

class StartPracticeSessionRequest(BaseModel):
    prompt_side: CardSide
    words_per_session: SessionSize

class StartReviewSessionRequest(BaseModel):
    prompt_side: CardSide
    words_per_session: SessionSize

class ReviewSideSummary(BaseModel):
    # Срок уже наступил
    due_now: Counter
    # Срок наступает до конца дня пользователя, включая due_now
    due_today: Counter
    # Ближайший срок после текущего момента, None — больше нечего повторять
    next_due_at: AwareDatetime | None

class ReviewSidesSummary(BaseModel):
    front: ReviewSideSummary
    back: ReviewSideSummary

class ActiveReviewSessionResponse(BaseModel):
    training_session_uuid: UUID7
    prompt_side: CardSide
    answered_count: Counter
    total_count: SessionSize

class ReviewSummaryResponse(BaseModel):
    timezone: Timezone
    # Ключ — prompt_side, с которой стартует сессия повторения
    sides: ReviewSidesSummary
    active_session: ActiveReviewSessionResponse | None

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
