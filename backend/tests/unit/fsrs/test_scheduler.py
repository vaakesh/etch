from datetime import UTC, datetime, timedelta

import pytest

from app.fsrs.params import STABILITY_MIN, FSRSParams
from app.fsrs.scheduler import Scheduler
from app.fsrs.types import Card, CardState, Rating, ReviewLog

START = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def make_review_card() -> Card:
    # Карточка после GOOD, GOOD, GOOD по расписанию (значения из эталона)
    return Card(
        state=CardState.REVIEW,
        step=None,
        stability=10.971048263078135,
        difficulty=2.1043313908464483,
        due=START + timedelta(days=13, minutes=10),
        last_review=START + timedelta(days=2, minutes=10),
    )


def make_learning_card(step: int | None) -> Card:
    return Card(
        state=CardState.LEARNING,
        step=step,
        stability=2.3065,
        difficulty=2.118103970459016,
        due=START + timedelta(minutes=10),
        last_review=START,
    )


class TestSchedulerInit:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"learning_steps": (timedelta(0),)},
            {"relearning_steps": (timedelta(minutes=-1),)},
        ],
    )
    def test_rejects_non_positive_steps(self, kwargs):
        with pytest.raises(ValueError, match="must be positive"):
            Scheduler(**kwargs)


class TestReviewNewCard:
    @pytest.mark.parametrize(
        ("rating", "expected_step", "expected_delay"),
        [
            (Rating.AGAIN, 0, timedelta(minutes=1)),
            (Rating.HARD, 0, timedelta(minutes=5, seconds=30)),
            (Rating.GOOD, 1, timedelta(minutes=10)),
        ],
    )
    def test_stays_in_learning(self, rating, expected_step, expected_delay):
        card, _ = Scheduler().review(Card.new(START), rating, START)

        assert card.state == CardState.LEARNING
        assert card.step == expected_step
        assert card.due == START + expected_delay
        assert card.last_review == START

    def test_sets_initial_memory_state(self):
        card, _ = Scheduler().review(Card.new(START), Rating.GOOD, START)

        assert card.stability == 2.3065
        assert card.difficulty == pytest.approx(2.118103970459016, rel=1e-12)

    def test_easy_graduates_to_review_immediately(self):
        card, _ = Scheduler().review(Card.new(START), Rating.EASY, START)

        assert card.state == CardState.REVIEW
        assert card.step is None
        assert card.due == START + timedelta(days=8)

    def test_hard_with_single_step_uses_one_and_a_half_step(self):
        scheduler = Scheduler(learning_steps=(timedelta(minutes=10),))

        card, _ = scheduler.review(Card.new(START), Rating.HARD, START)

        assert card.step == 0
        assert card.due == START + timedelta(minutes=15)

    def test_graduates_immediately_without_learning_steps(self):
        scheduler = Scheduler(learning_steps=())

        card, _ = scheduler.review(Card.new(START), Rating.GOOD, START)

        assert card.state == CardState.REVIEW
        assert card.step is None
        assert card.due == START + timedelta(days=2)

    def test_does_not_modify_input_card(self):
        original = Card.new(START)

        Scheduler().review(original, Rating.GOOD, START)

        assert original == Card.new(START)

    def test_returns_review_log(self):
        _, log = Scheduler().review(Card.new(START), Rating.GOOD, START)

        assert log == ReviewLog(
            rating=Rating.GOOD,
            review_datetime=START,
            elapsed_days=None,
            state_before=CardState.LEARNING,
            stability_before=None,
            difficulty_before=None,
        )


class TestReviewLearningCard:
    def test_good_on_last_step_graduates_to_review(self):
        now = START + timedelta(minutes=10)

        card, _ = Scheduler().review(make_learning_card(step=1), Rating.GOOD, now)

        assert card.state == CardState.REVIEW
        assert card.step is None
        assert card.due == now + timedelta(days=2)

    def test_hard_on_later_step_repeats_current_step(self):
        now = START + timedelta(minutes=10)

        card, _ = Scheduler().review(make_learning_card(step=1), Rating.HARD, now)

        assert card.state == CardState.LEARNING
        assert card.step == 1
        assert card.due == now + timedelta(minutes=10)

    def test_again_returns_to_first_step(self):
        now = START + timedelta(minutes=10)

        card, _ = Scheduler().review(make_learning_card(step=1), Rating.AGAIN, now)

        assert card.state == CardState.LEARNING
        assert card.step == 0
        assert card.due == now + timedelta(minutes=1)

    def test_step_beyond_configured_steps_graduates_on_good(self):
        now = START + timedelta(minutes=10)

        card, _ = Scheduler().review(make_learning_card(step=5), Rating.GOOD, now)

        assert card.state == CardState.REVIEW
        assert card.step is None

    def test_rejects_learning_card_without_step(self):
        with pytest.raises(ValueError, match="must have a step"):
            Scheduler().review(make_learning_card(step=None), Rating.GOOD, START)


class TestReviewReviewCard:
    def test_good_on_time_matches_reference(self):
        card = make_review_card()

        result, _ = Scheduler().review(card, Rating.GOOD, card.due)

        assert result.state == CardState.REVIEW
        assert result.stability == pytest.approx(46.316858440073425, rel=1e-12)
        assert result.difficulty == pytest.approx(2.0974554287524403, rel=1e-12)
        assert result.due == card.due + timedelta(days=46)

    def test_again_moves_to_relearning(self):
        card = make_review_card()

        result, _ = Scheduler().review(card, Rating.AGAIN, card.due)

        assert result.state == CardState.RELEARNING
        assert result.step == 0
        assert result.stability == pytest.approx(1.53901253028147, rel=1e-12)
        assert result.difficulty == pytest.approx(7.389975788014609, rel=1e-12)
        assert result.due == card.due + timedelta(minutes=10)

    def test_again_without_relearning_steps_stays_in_review(self):
        card = make_review_card()
        scheduler = Scheduler(relearning_steps=())

        result, _ = scheduler.review(card, Rating.AGAIN, card.due)

        assert result.state == CardState.REVIEW
        assert result.step is None
        assert result.due == card.due + timedelta(days=2)

    def test_interval_is_capped_by_maximum_interval(self):
        card = make_review_card()
        scheduler = Scheduler(params=FSRSParams(maximum_interval=5))

        result, _ = scheduler.review(card, Rating.EASY, card.due)

        assert result.due == card.due + timedelta(days=5)

    def test_review_log_keeps_state_before_review(self):
        card = make_review_card()

        _, log = Scheduler().review(card, Rating.GOOD, card.due)

        assert log == ReviewLog(
            rating=Rating.GOOD,
            review_datetime=card.due,
            elapsed_days=11,
            state_before=CardState.REVIEW,
            stability_before=10.971048263078135,
            difficulty_before=2.1043313908464483,
        )


class TestReviewRelearningCard:
    def test_good_on_last_step_returns_to_review(self):
        card = Card(
            state=CardState.RELEARNING,
            step=0,
            stability=1.53901253028147,
            difficulty=7.389975788014609,
            due=START + timedelta(minutes=10),
            last_review=START,
        )

        result, _ = Scheduler().review(card, Rating.GOOD, card.due)

        assert result.state == CardState.REVIEW
        assert result.step is None
        assert result.stability == pytest.approx(1.5718415897918614, rel=1e-12)
        assert result.due == card.due + timedelta(days=2)


class TestSameDayAgain:
    def test_repeated_same_day_again_keeps_minimum_stability(self):
        scheduler = Scheduler()
        card = Card.new(START)
        now = START

        for _ in range(10):
            card, _ = scheduler.review(card, Rating.AGAIN, now)
            now += timedelta(minutes=5)

        assert card.stability == STABILITY_MIN


class TestSameDayEasyLimit:
    def make_easy_review_card(self) -> Card:
        # Карточка после первого EASY: S = w3, D обрезана до 1
        return Card(
            state=CardState.REVIEW,
            step=None,
            stability=8.2956,
            difficulty=1.0,
            due=START + timedelta(days=8),
            last_review=START,
        )

    def test_same_day_easy_updates_memory_like_good(self):
        card = self.make_easy_review_card()
        now = START + timedelta(minutes=3)

        result, _ = Scheduler().review(card, Rating.EASY, now)

        assert result.stability == 8.2956
        assert result.difficulty == 1.0
        assert result.due == now + timedelta(days=8)

    def test_disabled_limit_keeps_reference_easy_growth(self):
        card = self.make_easy_review_card()
        now = START + timedelta(minutes=3)
        scheduler = Scheduler(limit_same_day_easy=False)

        result, _ = scheduler.review(card, Rating.EASY, now)

        assert result.stability == pytest.approx(13.046064691177456, rel=1e-12)
        assert result.due == now + timedelta(days=13)

    def test_repeated_same_day_easy_does_not_inflate_stability(self):
        scheduler = Scheduler()
        card, _ = scheduler.review(Card.new(START), Rating.EASY, START)
        now = START

        for _ in range(99):
            now += timedelta(minutes=3)
            card, _ = scheduler.review(card, Rating.EASY, now)

        assert card.stability == 8.2956
        assert card.due == now + timedelta(days=8)

    def test_same_day_easy_still_skips_learning_steps(self):
        card = make_learning_card(step=0)
        now = START + timedelta(minutes=1)

        result, _ = Scheduler().review(card, Rating.EASY, now)

        assert result.state == CardState.REVIEW
        assert result.step is None

    def test_review_log_keeps_original_rating(self):
        card = self.make_easy_review_card()
        now = START + timedelta(minutes=3)

        _, log = Scheduler().review(card, Rating.EASY, now)

        assert log.rating == Rating.EASY

    def test_first_answer_easy_is_not_limited(self):
        card, _ = Scheduler().review(Card.new(START), Rating.EASY, START)

        assert card.stability == 8.2956

    def test_easy_after_a_day_or_more_is_not_limited(self):
        card = self.make_easy_review_card()
        now = START + timedelta(days=8)

        limited, _ = Scheduler().review(card, Rating.EASY, now)
        reference, _ = Scheduler(limit_same_day_easy=False).review(
            card, Rating.EASY, now
        )

        assert limited == reference


class TestReviewErrors:
    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            Scheduler().review(Card.new(START), Rating.GOOD, datetime(2026, 1, 1))

    def test_rejects_review_before_last_review(self):
        card = make_review_card()

        with pytest.raises(ValueError, match="earlier than last review"):
            Scheduler().review(card, Rating.GOOD, START)

    def test_rejects_memory_state_without_last_review(self):
        card = Card(
            state=CardState.REVIEW,
            step=None,
            stability=10.0,
            difficulty=5.0,
            due=START,
            last_review=None,
        )

        with pytest.raises(ValueError, match="no last_review"):
            Scheduler().review(card, Rating.GOOD, START)


class TestGetRetrievability:
    def test_returns_zero_for_new_card(self):
        result = Scheduler().get_retrievability(Card.new(START), START)

        assert result == 0.0

    @pytest.mark.parametrize(
        ("elapsed", "expected"),
        [
            (timedelta(0), 1.0),
            (timedelta(hours=23), 1.0),
            (timedelta(days=1), 0.9468474993825461),
            (timedelta(days=10), 0.7743669167614039),
        ],
    )
    def test_uses_whole_days_since_last_review(self, elapsed, expected):
        card = make_learning_card(step=1)

        result = Scheduler().get_retrievability(card, START + elapsed)

        assert result == pytest.approx(expected, rel=1e-12)
