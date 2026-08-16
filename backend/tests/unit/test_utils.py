from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.errors import RequestValueError
from app.common.utils import (
    calculate_accuracy,
    format_duration,
    decode_cursor,
    encode_cursor,
    utcnow,
    make_user_deck_identity,
)
from app.auth.utils import (
    hash_password,
    verify_password,
)
from argon2.exceptions import InvalidHashError

from types import SimpleNamespace

class TestUtcnow:
    def test_returns_current_utc_datetime(self):
        before = datetime.now(UTC)

        result = utcnow()

        after = datetime.now(UTC)
        assert result.tzinfo is UTC
        assert before <= result <= after

class TestFormatDuration:
    @pytest.mark.parametrize(
        ("duration", "expected"),
        [
            (0.0, "\x1b[32m0.000s\x1b[0m"),
            (0.3, "\x1b[32m0.300s\x1b[0m"),
            (0.3001, "\x1b[33m0.300s\x1b[0m"),
            (1.0, "\x1b[33m1.000s\x1b[0m"),
            (1.0001, "\x1b[31m1.000s\x1b[0m"),
            (1.2345, "\x1b[31m1.234s\x1b[0m"),
        ],
    )
    def test_formats_duration_with_color(self, duration: float, expected: str):
        assert format_duration(duration) == expected

class TestCursor:
    @pytest.mark.parametrize(
        "original_time",
        [
            datetime(2026, 8, 14, 12, 30, tzinfo=UTC),
            datetime(
                2026,
                8,
                14,
                15,
                30,
                tzinfo=timezone(timedelta(hours=3)),
            ),
        ],
    )
    def test_round_trip(self, original_time: datetime):
        cursor = encode_cursor(original_time, entity_id=42)

        assert decode_cursor(cursor) == (original_time, 42)

    @pytest.mark.parametrize("invalid_id", [0, -1])
    def test_rejects_non_positive_id(self, invalid_id: int):
        moment = datetime(2026, 8, 14, tzinfo=UTC)
        cursor = encode_cursor(moment, entity_id=invalid_id)

        with pytest.raises(
            RequestValueError,
            match="Cursor id must be positive",
        ) as exc_info:
            decode_cursor(cursor)

        assert exc_info.value.failed_field == "cursor"

    def test_rejects_datetime_without_timezone(self):
        moment_without_timezone = datetime(2026, 8, 14, 12, 30)
        cursor = encode_cursor(moment_without_timezone, entity_id=42)

        with pytest.raises(
            RequestValueError,
            match="Cursor datetime must include timezone",
        ) as exc_info:
            decode_cursor(cursor)

        assert exc_info.value.failed_field == "cursor"

    def test_rejects_malformed_value(self):
        with pytest.raises(
            RequestValueError,
            match="Invalid cursor format",
        ) as exc_info:
            decode_cursor("definitely-not-a-cursor")

        assert exc_info.value.failed_field == "cursor"

class TestCalculateAccuracy:
    @pytest.mark.parametrize(
        ("correct_count", "wrong_count", "expected"),
        [
            (0, 0, 0),
            (1, 0, 100),
            (0, 1, 0),
            (1, 1, 50),
            (3, 1, 75),
            (1, 2, 33),
            (2, 1, 66),
            (99, 1, 99),
        ],
    )
    def test_calculates_accuracy(
        self,
        correct_count: int,
        wrong_count: int,
        expected: int,
    ):
        user_deck = SimpleNamespace(
            correct_count=correct_count,
            wrong_count=wrong_count,
        )

        assert calculate_accuracy(user_deck) == expected

    def test_returns_zero_when_user_deck_is_none(self):
        assert calculate_accuracy(None) == 0

class TestMakeUserDeckIdentity:
    @pytest.mark.parametrize(
        ("user_id", "deck_id"),
        [
            (1, 1),
            (1, 42),
            (42, 1),
            (123, 456),
        ],
    )
    def test_returns_user_and_deck_id_tuple(
        self,
        user_id: int,
        deck_id: int,
    ):
        assert make_user_deck_identity(user_id, deck_id) == (
            user_id,
            deck_id,
        )

class TestPassword:
    def test_hash_password_returns_hash_different_from_password(self):
        password = "secure-password"

        password_hash = hash_password(password)

        assert password_hash != password
        assert isinstance(password_hash, str)

    def test_verify_password_returns_true_for_correct_password(self):
        password = "secure-password"
        password_hash = hash_password(password)

        result = verify_password(password, password_hash)

        assert result is True

    def test_verify_password_returns_false_for_wrong_password(self):
        password_hash = hash_password("correct-password")

        result = verify_password("wrong-password", password_hash)

        assert result is False

    def test_verify_password_raises_for_invalid_hash(self):
        with pytest.raises(InvalidHashError):
            verify_password("password", "not-a-valid-argon2-hash")