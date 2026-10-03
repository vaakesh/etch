import pytest
from pydantic import TypeAdapter, ValidationError

from app.users.types import NormalizedEmail


class TestNormalizedEmail:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("alice@example.com", "alice@example.com"),
            ("ALICE@EXAMPLE.COM", "alice@example.com"),
            (" \tALICE@EXAMPLE.COM\n", "alice@example.com"),
            ("Alice+News@Example.com", "alice+news@example.com"),
        ],
    )
    def test_normalizes_valid_email(self, value, expected):
        adapter = TypeAdapter(NormalizedEmail)

        result = adapter.validate_python(value)

        assert result == expected

    @pytest.mark.parametrize(
        "value",
        ["", " \t\n", "alice", "@example.com", "alice@", "ali ce@example.com",
         "ali\tce@example.com", "ali\nce@example.com", "alice@exa mple.com"],
    )
    def test_rejects_empty_or_invalid_email(self, value):
        adapter = TypeAdapter(NormalizedEmail)

        with pytest.raises(ValidationError):
            adapter.validate_python(value)

    def test_accepts_254_character_address(self):
        value = "a" * 64 + "@" + "b" * 63 + "." + "c" * 63 + "." + "d" * 57 + ".com"
        adapter = TypeAdapter(NormalizedEmail)

        result = adapter.validate_python(value)

        assert result == value
        assert len(result) == 254

    @pytest.mark.parametrize("length", [255, 256])
    def test_rejects_address_exceeding_emailstr_limit(self, length):
        value = "a" * 64 + "@" + "b" * 63 + "." + "c" * 63 + "." + "d" * (length - 197) + ".com"
        adapter = TypeAdapter(NormalizedEmail)

        with pytest.raises(ValidationError):
            adapter.validate_python(value)

    def test_declares_255_character_storage_limit(self):
        adapter = TypeAdapter(NormalizedEmail)

        schema = adapter.json_schema()

        assert schema["maxLength"] == 255
