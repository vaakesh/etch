import math

from app.fsrs.params import (
    DIFFICULTY_MAX,
    DIFFICULTY_MIN,
    STABILITY_MIN,
    FSRSParams,
)
from app.fsrs.types import Rating


def _clamp_difficulty(difficulty: float) -> float:
    return min(max(difficulty, DIFFICULTY_MIN), DIFFICULTY_MAX)


def retrievability(
    elapsed_days: float,
    stability: float,
    params: FSRSParams,
) -> float:
    """Вероятность вспомнить через t дней, R(0) = 1, R(S) = 0.9"""
    elapsed_days = max(elapsed_days, 0.0)
    return (1 + params.factor * elapsed_days / stability) ** params.decay


def next_interval(stability: float, params: FSRSParams) -> int:
    # Обратная функция к кривой: через сколько дней R упадет до desired_retention
    r = params.desired_retention
    raw = stability / params.factor * (r ** (1 / params.decay) - 1)
    return min(max(round(raw), 1), params.maximum_interval)


def initial_stability(rating: Rating, params: FSRSParams) -> float:
    return max(params.w[rating - 1], STABILITY_MIN)


def initial_difficulty(
    rating: Rating,
    params: FSRSParams,
    *,
    clamp: bool = True,
) -> float:
    w = params.w
    difficulty = w[4] - math.exp(w[5] * (rating - 1)) + 1
    return _clamp_difficulty(difficulty) if clamp else difficulty


def next_difficulty(
    difficulty: float,
    rating: Rating,
    params: FSRSParams,
) -> float:
    w = params.w
    # AGAIN (G = 1) увеличивает D, GOOD не меняет, EASY уменьшает
    delta = -w[6] * (rating - 3)
    # Линейное затухание: чем ближе D к 10, тем меньше шаг
    damped = difficulty + delta * (10 - difficulty) / 9
    # Возврат к среднему: D немного тянется к начальной D для EASY
    target = initial_difficulty(Rating.EASY, params, clamp=False)
    reverted = w[7] * target + (1 - w[7]) * damped
    return _clamp_difficulty(reverted)


def next_recall_stability(
    difficulty: float,
    stability: float,
    r: float,
    rating: Rating,
    params: FSRSParams,
) -> float:
    w = params.w
    hard_penalty = w[15] if rating == Rating.HARD else 1.0
    easy_bonus = w[16] if rating == Rating.EASY else 1.0
    growth = (
        math.exp(w[8])
        * (11 - difficulty)  # трудное слово растёт медленнее
        * stability ** (-w[9])  # большая S растёт медленнее
        * (math.exp(w[10] * (1 - r)) - 1)  # чем ниже была R, тем больше прирост
        * hard_penalty
        * easy_bonus
    )
    return stability * (1 + growth)


def next_forget_stability(
    difficulty: float,
    stability: float,
    r: float,
    params: FSRSParams,
) -> float:
    w = params.w
    long_term = (
        w[11]
        * difficulty ** (-w[12])
        * ((stability + 1) ** w[13] - 1)
        * math.exp(w[14] * (1 - r))
    )
    # После забывания S не должна получиться больше, чем после Again в тот же день
    short_term_cap = stability / math.exp(w[17] * w[18])
    return min(long_term, short_term_cap)


def next_short_term_stability(
    stability: float,
    rating: Rating,
    params: FSRSParams,
) -> float:
    # Повтор в тот же день: кривая забывания тут не работает, используется отдельная формула
    w = params.w
    increase = math.exp(w[17] * (rating - 3 + w[18])) * stability ** (-w[19])
    if rating != Rating.AGAIN:
        increase = max(increase, 1.0)  # уменьшить S в тот же день может только AGAIN
    # AGAIN подряд в тот же день уменьшает S каждый раз, нижняя граница как в эталоне
    return max(stability * increase, STABILITY_MIN)


def next_stability(
    difficulty: float,
    stability: float,
    r: float,
    rating: Rating,
    params: FSRSParams,
) -> float:
    if rating == Rating.AGAIN:
        new_stability = next_forget_stability(difficulty, stability, r, params)
    else:
        new_stability = next_recall_stability(difficulty, stability, r, rating, params)
    return max(new_stability, STABILITY_MIN)
