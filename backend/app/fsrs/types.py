from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum, StrEnum


class Rating(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


class CardState(StrEnum):
    LEARNING = "learning"
    REVIEW = "review"
    RELEARNING = "relearning"


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Card:
    state: CardState
    step: int | None
    stability: float | None
    difficulty: float | None
    due: datetime
    last_review: datetime | None

    @classmethod
    def new(cls, now: datetime) -> Card:
        # new card, S = D = None, step = 0
        return cls(
            state=CardState.LEARNING,
            step=0,
            stability=None,
            difficulty=None,
            due=ensure_aware_utc(now),
            last_review=None,
        )


@dataclass(frozen=True, slots=True)
class ReviewLog:
    rating: Rating
    review_datetime: datetime
    elapsed_days: int | None
    state_before: CardState
    stability_before: float | None
    difficulty_before: float | None
