from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from app.fsrs import model
from app.fsrs.params import FSRSParams
from app.fsrs.types import Card, CardState, Rating, ReviewLog, ensure_aware_utc

DEFAULT_LEARNING_STEPS = (timedelta(minutes=1), timedelta(minutes=10))
DEFAULT_RELEARNING_STEPS = (timedelta(minutes=10),)

type Transition = tuple[CardState, int | None, timedelta]


@dataclass(frozen=True, slots=True)
class Scheduler:
    params: FSRSParams = field(default_factory=FSRSParams)
    learning_steps: tuple[timedelta, ...] = DEFAULT_LEARNING_STEPS
    relearning_steps: tuple[timedelta, ...] = DEFAULT_RELEARNING_STEPS
    # Краткосрочная формула для EASY почти не насыщается: 100 x EASY за день дают
    # S ~ 8000 дней. Повтор в тот же день не говорит о памяти больше, чем GOOD,
    # поэтому для обновления S и D EASY понижается до GOOD. False = как в эталоне.
    limit_same_day_easy: bool = True

    def __post_init__(self) -> None:
        for steps in (self.learning_steps, self.relearning_steps):
            if any(step <= timedelta(0) for step in steps):
                raise ValueError("learning steps must be positive")

    def get_retrievability(self, card: Card, now: datetime) -> float:
        if card.last_review is None or card.stability is None:
            return 0.0
        elapsed_days = max((ensure_aware_utc(now) - card.last_review).days, 0)
        return model.retrievability(
            elapsed_days=elapsed_days,
            stability=card.stability,
            params=self.params,
        )

    def review(
        self,
        card: Card,
        rating: Rating,
        now: datetime,
    ) -> tuple[Card, ReviewLog]:
        now = ensure_aware_utc(now)
        elapsed_days = None
        if card.last_review is not None:
            if now < card.last_review:
                raise ValueError("review time is earlier than last review")
            # целые дни, 23 часа - 0 дней, повтор в тот же день
            elapsed_days = (now - card.last_review).days

        stability, difficulty = self._next_memory(
            card,
            rating,
            now,
            elapsed_days,
        )

        if card.state == CardState.REVIEW:
            state, step, interval = self._review_transition(rating, stability)
        else:
            steps = (
                self.learning_steps
                if card.state == CardState.LEARNING
                else self.relearning_steps
            )
            state, step, interval = self._step_transition(
                card.state, card.step, rating, stability, steps
            )

        new_card = replace(
            card,
            state=state,
            step=step,
            stability=stability,
            difficulty=difficulty,
            due=now + interval,
            last_review=now,
        )
        log = ReviewLog(
            rating=rating,
            review_datetime=now,
            elapsed_days=elapsed_days,
            state_before=card.state,
            stability_before=card.stability,
            difficulty_before=card.difficulty,
        )
        return new_card, log

    def _next_memory(
        self,
        card: Card,
        rating: Rating,
        now: datetime,
        elapsed_days: int | None,
    ) -> tuple[float, float]:
        p = self.params
        # Первый ответ: памяти ещё нет, берём начальные значения
        if card.stability is None or card.difficulty is None:
            return model.initial_stability(rating, p), model.initial_difficulty(rating, p)
        if elapsed_days is None:
            raise ValueError("card has memory state but no last_review")

        if elapsed_days < 1:
            # Только для памяти: переход по шагам использует исходную оценку
            memory_rating = rating
            if self.limit_same_day_easy and rating == Rating.EASY:
                memory_rating = Rating.GOOD
            difficulty = model.next_difficulty(card.difficulty, memory_rating, p)
            stability = model.next_short_term_stability(card.stability, memory_rating, p)
        else:
            # D всегда обновляется от старой D. S тоже считается от старой D
            difficulty = model.next_difficulty(card.difficulty, rating, p)
            r = self.get_retrievability(card, now)
            stability = model.next_stability(card.difficulty, card.stability, r, rating, p)
        return stability, difficulty

    def _review_interval(self, stability: float) -> timedelta:
        return timedelta(days=model.next_interval(stability, self.params))

    def _review_transition(self, rating: Rating, stability: float) -> Transition:
        # Забыл выученное слово: уходит на переобучение, если шаги переобучения заданы
        if rating == Rating.AGAIN and self.relearning_steps:
            return CardState.RELEARNING, 0, self.relearning_steps[0]
        return CardState.REVIEW, None, self._review_interval(stability)

    def _step_transition(
        self,
        state: CardState,
        step: int | None,
        rating: Rating,
        stability: float,
        steps: tuple[timedelta, ...],
    ) -> Transition:
        if step is None:
            raise ValueError(f"card in state {state} must have a step")

        graduate: Transition = (CardState.REVIEW, None, self._review_interval(stability))
        # Шагов нет, или их стало меньше, чем было при создании карточки
        if not steps or (step >= len(steps) and rating != Rating.AGAIN):
            return graduate

        if rating == Rating.AGAIN:
            return state, 0, steps[0]
        if rating == Rating.HARD:
            # Шаг не меняется, интервал чуть больше текущего шага
            if step == 0 and len(steps) == 1:
                return state, step, steps[0] * 1.5
            if step == 0:
                return state, step, (steps[0] + steps[1]) / 2
            return state, step, steps[step]
        if rating == Rating.GOOD:
            if step + 1 == len(steps):
                return graduate
            return state, step + 1, steps[step + 1]
        return graduate  # EASY: сразу в REVIEW
