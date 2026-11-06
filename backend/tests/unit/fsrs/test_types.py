from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.fsrs.types import Card, CardState, ensure_aware_utc


class TestEnsureAwareUtc:
    def test_converts_other_timezone_to_utc(self):
        moscow = timezone(timedelta(hours=3))

        result = ensure_aware_utc(datetime(2026, 1, 1, 15, 0, tzinfo=moscow))

        assert result == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        assert result.tzinfo is UTC

    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            ensure_aware_utc(datetime(2026, 1, 1, 12, 0))


class TestCardNew:
    def test_creates_learning_card_without_memory_state(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

        card = Card.new(now)

        assert card == Card(
            state=CardState.LEARNING,
            step=0,
            stability=None,
            difficulty=None,
            due=now,
            last_review=None,
        )

    def test_rejects_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            Card.new(datetime(2026, 1, 1, 12, 0))
