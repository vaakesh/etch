import pytest
from pydantic import TypeAdapter, ValidationError

from app.common.types import Username


class TestUsername:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("Alice", "Alice"),
            (" \tAlice-01_\n", "Alice-01_"),
            ("a_1", "a_1"),
            ("Abcdefghijklmnopq8", "Abcdefghijklmnopq8"),
            ("---", "---"),
        ],
    )
    def test_accepts_allowed_characters_and_preserves_case(self, value, expected):
        adapter = TypeAdapter(Username)

        result = adapter.validate_python(value)

        assert result == expected

    @pytest.mark.parametrize(
        "value",
        ["ab", "abcdefghijklmnopqrs", "", "   ", "Алиса", "Alice🙂",
         "alice.name", "alice/name", "ali ce", "ali\tce", "ali\nce"],
    )
    def test_rejects_invalid_length_or_characters(self, value):
        adapter = TypeAdapter(Username)

        with pytest.raises(ValidationError):
            adapter.validate_python(value)
