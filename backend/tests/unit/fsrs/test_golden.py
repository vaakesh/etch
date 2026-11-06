"""Сверка с эталонной библиотекой py-fsrs 6.3.2.

Ожидаемые значения получены один раз скриптом вне репозитория:
Scheduler(desired_retention=0.9, learning_steps=(1m, 10m), relearning_steps=(10m,),
maximum_interval=36500, enable_fuzzing=False), первый ответ в START.
Библиотека в проект не подключается. В эталоне нет защиты от EASY в тот же день,
поэтому здесь она выключена (limit_same_day_easy=False).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.fsrs.scheduler import Scheduler
from app.fsrs.types import Card, CardState, Rating

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

A, H, G, E = Rating.AGAIN, Rating.HARD, Rating.GOOD, Rating.EASY
LEARNING = CardState.LEARNING
REVIEW = CardState.REVIEW
RELEARNING = CardState.RELEARNING


def at(days: int = 0, seconds: int = 0) -> timedelta:
    return timedelta(days=days, seconds=seconds)


# Шаг: (оценка, задержка от прошлого ответа или None = ответ ровно в due,
#        состояние, step, S, D, due относительно START)
# fmt: off
SCENARIOS = {
    "good_on_time": [
        (G, None, LEARNING, 1, 2.3065, 2.118103970459016, at(0, 600)),
        (G, None, REVIEW, None, 2.3065, 2.111214235785395, at(2, 600)),
        (G, None, REVIEW, None, 10.971048263078135, 2.1043313908464483, at(13, 600)),
        (G, None, REVIEW, None, 46.316858440073425, 2.0974554287524403, at(59, 600)),
        (G, None, REVIEW, None, 162.99981577472244, 2.0905863426205262, at(222, 600)),
        (G, None, REVIEW, None, 497.8765551245907, 2.083724125574744, at(720, 600)),
    ],
    "again_then_good": [
        (A, None, LEARNING, 0, 0.212, 6.4133, at(0, 60)),
        (G, None, LEARNING, 1, 0.24668918777567272, 6.402115069296838, at(0, 660)),
        (G, None, REVIEW, None, 0.2842063592758949, 6.3909413235243795, at(1, 660)),
        (G, None, REVIEW, None, 2.1520782454047453, 6.379778751497693, at(3, 660)),
        (G, None, REVIEW, None, 6.624321210928598, 6.368627342043034, at(10, 660)),
    ],
    "easy_first": [
        (E, None, REVIEW, None, 8.2956, 1.0, at(8)),
        (G, None, REVIEW, None, 38.90514998232684, 1.0, at(47)),
        (G, None, REVIEW, None, 153.00006571733257, 1.0, at(200)),
        (G, None, REVIEW, None, 509.55021966881696, 1.0, at(710)),
    ],
    "hard_first": [
        (H, None, LEARNING, 0, 1.2931, 5.112170705601056, at(0, 330)),
        (H, None, LEARNING, 0, 1.2931, 6.7404595108297, at(0, 660)),
        (G, None, LEARNING, 1, 1.3358997622047517, 6.728947420615708, at(0, 1260)),
        (G, None, REVIEW, None, 1.3771622371865915, 6.717446842491931, at(1, 1260)),
        (G, None, REVIEW, None, 3.754040668890707, 6.705957764946278, at(5, 1260)),
    ],
    "lapse": [
        (G, None, LEARNING, 1, 2.3065, 2.118103970459016, at(0, 600)),
        (G, None, REVIEW, None, 2.3065, 2.111214235785395, at(2, 600)),
        (G, None, REVIEW, None, 10.971048263078135, 2.1043313908464483, at(13, 600)),
        (A, None, RELEARNING, 0, 1.53901253028147, 7.389975788014609, at(13, 1200)),
        (G, None, REVIEW, None, 1.5718415897918614, 7.377814181523433, at(15, 1200)),
        (G, None, REVIEW, None, 4.934768723890772, 7.365664736638748, at(20, 1200)),
    ],
    "same_day_in_review": [
        (E, None, REVIEW, None, 8.2956, 1.0, at(8)),
        (G, at(0, 10800), REVIEW, None, 8.2956, 1.0, at(8, 10800)),
        (A, at(0, 7200), RELEARNING, 0, 2.5625081682260777, 7.0269895692968385,
         at(0, 18600)),
        (G, at(0, 600), REVIEW, None, 2.5625081682260777, 7.0151909490243805,
         at(3, 18600)),
        (G, at(30), REVIEW, None, 19.169394671892178, 7.003404127372194,
         at(49, 18600)),
    ],
    "overdue": [
        (G, None, LEARNING, 1, 2.3065, 2.118103970459016, at(0, 600)),
        (G, None, REVIEW, None, 2.3065, 2.111214235785395, at(2, 600)),
        (G, at(100), REVIEW, None, 51.096250058923516, 2.1043313908464483,
         at(151, 600)),
        (H, at(400), REVIEW, None, 284.5973518307871, 4.743715608383524,
         at(785, 600)),
    ],
    "mixed": [
        (G, None, LEARNING, 1, 2.3065, 2.118103970459016, at(0, 600)),
        (A, None, LEARNING, 0, 0.7750839828558984, 7.394502741279718, at(0, 660)),
        (G, None, LEARNING, 1, 0.8281648000472626, 7.382336607835277, at(0, 1260)),
        (H, None, LEARNING, 1, 0.8281648000472626, 8.24750142646382, at(0, 1860)),
        (E, None, REVIEW, None, 1.5156418705173513, 7.647126438918395, at(2, 1860)),
        (G, None, REVIEW, None, 4.610173550905246, 7.634707681776315, at(7, 1860)),
    ],
}
# fmt: on


@pytest.mark.parametrize("steps", SCENARIOS.values(), ids=SCENARIOS.keys())
def test_matches_reference_fsrs(steps):
    scheduler = Scheduler(limit_same_day_easy=False)
    card = Card.new(START)
    now = START
    actual_schedule = []
    actual_memory = []

    for rating, delay, *_ in steps:
        now = card.due if delay is None else now + delay
        card, _ = scheduler.review(card, rating, now)
        actual_schedule.append((card.state, card.step, card.due - START))
        actual_memory.extend((card.stability, card.difficulty))

    expected_schedule = [(state, step, due) for _, _, state, step, _, _, due in steps]
    expected_memory = [value for *_, s, d, _ in steps for value in (s, d)]
    assert actual_schedule == expected_schedule
    assert actual_memory == pytest.approx(expected_memory, rel=1e-9)
