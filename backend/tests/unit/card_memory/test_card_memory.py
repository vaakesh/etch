from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.card_memory.models import CardMemoryState
from app.card_memory.replay import ReviewEvent, replay_reviews
from app.card_memory.utils import (
    SCHEDULER,
    effective_rating,
    end_of_local_day,
    rating_from_answer,
    to_knowledge_percent,
)
from app.fsrs.types import Card, CardState, Rating
from app.training_sessions.models import CardSide

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
KEY = UUID("019a0000-0000-7000-8000-000000000001")
OTHER_KEY = UUID("019a0000-0000-7000-8000-000000000002")


def event(
    answered_at: datetime,
    rating: Rating = Rating.GOOD,
    user_id: int = 42,
    learning_key: UUID = KEY,
    prompt_side: CardSide = "front",
) -> ReviewEvent:
    return ReviewEvent(
        user_id=user_id,
        learning_key=learning_key,
        prompt_side=prompt_side,
        rating=rating,
        answered_at=answered_at,
    )


class TestRatingFromAnswer:
    @pytest.mark.parametrize(
        ("is_correct", "expected"),
        [(True, Rating.GOOD), (False, Rating.AGAIN)],
    )
    def test_maps_correctness_to_rating(self, is_correct, expected):
        assert rating_from_answer(is_correct) == expected


class TestToKnowledgePercent:
    @pytest.mark.parametrize(
        ("knowledge", "expected"),
        [
            pytest.param(None, 0, id="deck_not_in_result"),
            pytest.param(0.0, 0, id="nothing_learned"),
            pytest.param(0.6435, 64, id="rounds_down"),
            pytest.param(0.6456, 65, id="rounds_up"),
            pytest.param(1.0, 100, id="everything_fresh"),
            pytest.param(1.0000001, 100, id="clamped_above_100"),
            pytest.param(-0.0000001, 0, id="clamped_below_0"),
        ],
    )
    def test_converts_mean_retrievability_to_percent(self, knowledge, expected):
        assert to_knowledge_percent(knowledge) == expected


class TestEndOfLocalDay:
    @pytest.mark.parametrize(
        ("now", "timezone", "expected"),
        [
            pytest.param(
                datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
                "UTC",
                datetime(2026, 3, 11, 0, 0, tzinfo=UTC),
                id="utc",
            ),
            pytest.param(
                # 23:30 по Москве: до конца местных суток полчаса
                datetime(2026, 3, 10, 20, 30, tzinfo=UTC),
                "Europe/Moscow",
                datetime(2026, 3, 10, 21, 0, tzinfo=UTC),
                id="east_of_utc_late_evening",
            ),
            pytest.param(
                # 01:00 UTC — ещё вчерашний вечер в Нью-Йорке
                datetime(2026, 1, 15, 1, 0, tzinfo=UTC),
                "America/New_York",
                datetime(2026, 1, 15, 5, 0, tzinfo=UTC),
                id="west_of_utc_previous_local_day",
            ),
            pytest.param(
                # 8 марта 2026 в Нью-Йорке переводят часы: сутки длятся 23 часа
                datetime(2026, 3, 8, 12, 0, tzinfo=UTC),
                "America/New_York",
                datetime(2026, 3, 9, 4, 0, tzinfo=UTC),
                id="dst_start_short_day",
            ),
            pytest.param(
                # 1 ноября 2026 часы переводят назад: сутки длятся 25 часов
                datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
                "America/New_York",
                datetime(2026, 11, 2, 5, 0, tzinfo=UTC),
                id="dst_end_long_day",
            ),
        ],
    )
    def test_returns_next_local_midnight_in_utc(self, now, timezone, expected):
        result = end_of_local_day(now, timezone)

        assert result == expected
        assert result.tzinfo == UTC


class TestEffectiveRating:
    @pytest.mark.parametrize(
        ("is_correct", "expected"),
        [(True, Rating.GOOD), (False, Rating.AGAIN)],
    )
    def test_falls_back_to_correctness_without_self_rating(self, is_correct, expected):
        assert effective_rating(is_correct, None) == expected

    @pytest.mark.parametrize(
        ("is_correct", "self_rating", "expected"),
        [
            (True, 4, Rating.EASY),
            (True, 1, Rating.AGAIN),
            (False, 3, Rating.GOOD),
            (False, 2, Rating.HARD),
        ],
    )
    def test_self_rating_overrides_correctness(self, is_correct, self_rating, expected):
        assert effective_rating(is_correct, self_rating) == expected


class TestCardMemoryStateMapping:
    def test_round_trips_fsrs_card(self):
        card = Card(
            state=CardState.REVIEW,
            step=None,
            stability=10.971048263078135,
            difficulty=2.1043313908464483,
            due=START + timedelta(days=11),
            last_review=START,
        )
        memory = CardMemoryState(user_id=42, learning_key=KEY, prompt_side="front")

        memory.apply_fsrs_card(card)

        assert memory.to_fsrs_card() == card


class TestReplayReviews:
    def test_first_correct_answer_creates_learning_card(self):
        result = replay_reviews([event(START)], SCHEDULER)

        assert list(result) == [(42, KEY, "front")]
        card = result[(42, KEY, "front")]
        assert card.state == CardState.LEARNING
        assert card.step == 1
        assert card.stability == 2.3065
        assert card.difficulty == pytest.approx(2.118103970459016, rel=1e-12)
        assert card.due == START + timedelta(minutes=10)
        assert card.last_review == START

    def test_keeps_separate_memory_per_user_word_and_side(self):
        events = [
            event(START),
            event(START, user_id=43),
            event(START, learning_key=OTHER_KEY),
            event(START, prompt_side="back"),
        ]

        result = replay_reviews(events, SCHEDULER)

        assert set(result) == {
            (42, KEY, "front"),
            (43, KEY, "front"),
            (42, OTHER_KEY, "front"),
            (42, KEY, "back"),
        }

    def test_wrong_answer_after_review_moves_card_to_relearning(self):
        events = [
            event(START),
            event(START + timedelta(minutes=10)),
            event(START + timedelta(days=2, minutes=10), rating=Rating.AGAIN),
        ]

        result = replay_reviews(events, SCHEDULER)

        card = result[(42, KEY, "front")]
        assert card.state == CardState.RELEARNING
        assert card.step == 0

    def test_matches_step_by_step_updates_through_stored_state(self):
        # submit_answer на каждом ответе читает строку из БД, делает review и пишет
        # обратно. Пересборка должна дать тот же результат
        events = [
            event(START),
            event(START + timedelta(minutes=10)),
            event(START + timedelta(days=2, minutes=10), rating=Rating.AGAIN),
            event(START + timedelta(days=2, minutes=20), rating=Rating.HARD),
            event(START + timedelta(days=5), rating=Rating.EASY),
        ]
        memory = CardMemoryState(user_id=42, learning_key=KEY, prompt_side="front")
        memory.apply_fsrs_card(Card.new(START))

        for item in events:
            card, _ = SCHEDULER.review(memory.to_fsrs_card(), item.rating, item.answered_at)
            memory.apply_fsrs_card(card)

        result = replay_reviews(events, SCHEDULER)
        assert result[(42, KEY, "front")] == memory.to_fsrs_card()

    def test_returns_empty_result_for_empty_log(self):
        assert replay_reviews([], SCHEDULER) == {}
