from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.errors import RequestValueError
from app.utils import decode_cursor, encode_cursor, format_duration, utcnow


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

        result = decode_cursor(cursor)

        assert result == (original_time, 42)

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
