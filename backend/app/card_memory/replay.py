from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.fsrs.scheduler import Scheduler
from app.fsrs.types import Card, Rating
from app.training_sessions.models import CardSide

type MemoryKey = tuple[int, UUID, CardSide]


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    user_id: int
    learning_key: UUID
    prompt_side: CardSide
    rating: Rating
    answered_at: datetime


def replay_reviews(
    events: Iterable[ReviewEvent],
    scheduler: Scheduler,
) -> dict[MemoryKey, Card]:
    """Проигрывает журнал ответов, упорядоченный по answered_at.

    Делает те же шаги, что submit_answer: новая карточка создаётся в момент первого
    ответа, затем review с итоговой оценкой ответа.
    """
    cards: dict[MemoryKey, Card] = {}
    for event in events:
        key = (event.user_id, event.learning_key, event.prompt_side)
        card = cards.get(key) or Card.new(event.answered_at)
        cards[key], _ = scheduler.review(card, event.rating, event.answered_at)
    return cards
