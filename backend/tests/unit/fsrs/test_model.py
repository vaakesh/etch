import math

import pytest

from app.fsrs.model import (
    initial_difficulty,
    initial_stability,
    next_difficulty,
    next_interval,
    next_short_term_stability,
    next_stability,
    retrievability,
)
from app.fsrs.params import STABILITY_MIN, FSRSParams
from app.fsrs.types import Rating

PARAMS = FSRSParams()


class TestRetrievability:
    def test_returns_one_right_after_review(self):
        result = retrievability(0, 2.3065, PARAMS)

        assert result == 1.0

    @pytest.mark.parametrize("stability", [0.5, 2.3065, 10.0, 365.0])
    def test_returns_ninety_percent_when_elapsed_equals_stability(self, stability):
        result = retrievability(stability, stability, PARAMS)

        assert result == pytest.approx(0.9)

    @pytest.mark.parametrize(
        ("elapsed_days", "expected"),
        [
            (1, 0.9468474993825461),
            (3, 0.8809479557659419),
            (10, 0.7743669167614039),
            (100, 0.5589067446271925),
        ],
    )
    def test_matches_reference_forgetting_curve(self, elapsed_days, expected):
        result = retrievability(elapsed_days, 2.3065, PARAMS)

        assert result == pytest.approx(expected, rel=1e-12)

    def test_decreases_as_time_passes(self):
        earlier = retrievability(5, 10.0, PARAMS)
        later = retrievability(6, 10.0, PARAMS)

        assert later < earlier

    def test_treats_negative_elapsed_time_as_zero(self):
        result = retrievability(-3, 10.0, PARAMS)

        assert result == 1.0


class TestNextInterval:
    @pytest.mark.parametrize(
        ("stability", "expected"),
        [
            (2.3065, 2),
            (10.971048263078135, 11),
            (46.316858440073425, 46),
        ],
    )
    def test_equals_rounded_stability_at_default_retention(self, stability, expected):
        result = next_interval(stability, PARAMS)

        assert result == expected

    def test_lower_retention_gives_longer_interval(self):
        params = FSRSParams(desired_retention=0.8)

        result = next_interval(10.0, params)

        assert result == 33

    def test_returns_at_least_one_day(self):
        result = next_interval(0.01, PARAMS)

        assert result == 1

    def test_is_capped_by_maximum_interval(self):
        params = FSRSParams(maximum_interval=365)

        result = next_interval(10_000.0, params)

        assert result == 365


class TestInitialStability:
    @pytest.mark.parametrize(
        ("rating", "expected"),
        [
            (Rating.AGAIN, 0.212),
            (Rating.HARD, 1.2931),
            (Rating.GOOD, 2.3065),
            (Rating.EASY, 8.2956),
        ],
    )
    def test_returns_parameter_for_rating(self, rating, expected):
        result = initial_stability(rating, PARAMS)

        assert result == expected


class TestInitialDifficulty:
    @pytest.mark.parametrize(
        ("rating", "expected"),
        [
            (Rating.AGAIN, 6.4133),
            (Rating.HARD, 5.112170705601056),
            (Rating.GOOD, 2.118103970459016),
            (Rating.EASY, 1.0),
        ],
    )
    def test_returns_clamped_difficulty_for_rating(self, rating, expected):
        result = initial_difficulty(rating, PARAMS)

        assert result == pytest.approx(expected, rel=1e-12)

    def test_returns_raw_value_below_minimum_without_clamp(self):
        result = initial_difficulty(Rating.EASY, PARAMS, clamp=False)

        assert result == pytest.approx(7.4133 - math.exp(0.8334 * 3))


class TestNextDifficulty:
    def test_good_matches_reference(self):
        result = next_difficulty(2.118103970459016, Rating.GOOD, PARAMS)

        assert result == pytest.approx(2.111214235785395, rel=1e-12)

    def test_again_increases_difficulty(self):
        result = next_difficulty(5.0, Rating.AGAIN, PARAMS)

        assert result > 5.0

    def test_easy_decreases_difficulty(self):
        result = next_difficulty(5.0, Rating.EASY, PARAMS)

        assert result < 5.0

    def test_easy_at_minimum_stays_at_minimum(self):
        result = next_difficulty(1.0, Rating.EASY, PARAMS)

        assert result == 1.0

    def test_again_at_maximum_does_not_exceed_maximum(self):
        result = next_difficulty(10.0, Rating.AGAIN, PARAMS)

        assert result <= 10.0


class TestNextStability:
    def test_again_decreases_stability(self):
        result = next_stability(5.0, 10.0, 0.9, Rating.AGAIN, PARAMS)

        assert result < 10.0

    @pytest.mark.parametrize("rating", [Rating.HARD, Rating.GOOD, Rating.EASY])
    def test_successful_answer_increases_stability(self, rating):
        result = next_stability(5.0, 10.0, 0.9, rating, PARAMS)

        assert result > 10.0

    def test_orders_growth_easy_good_hard(self):
        hard = next_stability(5.0, 10.0, 0.9, Rating.HARD, PARAMS)
        good = next_stability(5.0, 10.0, 0.9, Rating.GOOD, PARAMS)
        easy = next_stability(5.0, 10.0, 0.9, Rating.EASY, PARAMS)

        assert hard < good < easy

    def test_lower_retrievability_gives_bigger_growth(self):
        recalled_early = next_stability(5.0, 10.0, 0.95, Rating.GOOD, PARAMS)
        recalled_late = next_stability(5.0, 10.0, 0.7, Rating.GOOD, PARAMS)

        assert recalled_late > recalled_early

    def test_never_goes_below_minimum(self):
        result = next_stability(10.0, STABILITY_MIN, 0.0, Rating.AGAIN, PARAMS)

        assert result == STABILITY_MIN


class TestNextShortTermStability:
    @pytest.mark.parametrize(
        ("stability", "rating", "expected"),
        [
            (8.2956, Rating.AGAIN, 2.5625081682260777),
            (1.2931, Rating.HARD, 1.2931),
            (8.2956, Rating.GOOD, 8.2956),
            (0.212, Rating.GOOD, 0.24668918777567272),
        ],
    )
    def test_matches_reference(self, stability, rating, expected):
        result = next_short_term_stability(stability, rating, PARAMS)

        assert result == pytest.approx(expected, rel=1e-12)

    @pytest.mark.parametrize("rating", [Rating.HARD, Rating.GOOD, Rating.EASY])
    def test_successful_answer_does_not_decrease_stability(self, rating):
        result = next_short_term_stability(50.0, rating, PARAMS)

        assert result >= 50.0

    def test_again_never_goes_below_minimum(self):
        result = next_short_term_stability(STABILITY_MIN, Rating.AGAIN, PARAMS)

        assert result == STABILITY_MIN
