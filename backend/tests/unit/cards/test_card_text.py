import pytest
from pydantic import TypeAdapter, ValidationError

from app.cards.schemas import CreateCardRequest
from app.common.types import CardText


class TestCardText:
    @pytest.mark.parametrize(("value", "expected"), [
        ("Word", "Word"),
        ("  Слово  ", "Слово"),
        ("\u00a0日本語 🙂\u2003", "日本語 🙂"),
        (" \nFirst\n\tSecond  line\r\nThird\t ", "First\n\tSecond  line\r\nThird"),
        ("a", "a"),
        ("🙂" * 255, "🙂" * 255),
    ])
    def test_preserves_content_and_trims_edges(self, value, expected):
        adapter = TypeAdapter(CardText)

        result = adapter.validate_python(value)

        assert result == expected

    @pytest.mark.parametrize("value", ["", " \t\n\u00a0\u2003", "a" * 256, None])
    def test_rejects_empty_oversized_or_null_text(self, value):
        adapter = TypeAdapter(CardText)

        with pytest.raises(ValidationError):
            adapter.validate_python(value)


class TestCreateCardText:
    @pytest.mark.parametrize("field", ["front_text", "back_text"])
    def test_rejects_empty_side(self, field):
        payload = {"front_text": "Word", "back_text": "Слово", field: " \n "}

        with pytest.raises(ValidationError) as error:
            CreateCardRequest(**payload)

        assert error.value.errors()[0]["loc"] == (field,)

    def test_accepts_identical_sides_and_preserves_case(self):
        payload = {"front_text": "  Radio  ", "back_text": "\tRadio\n"}

        result = CreateCardRequest(**payload)

        assert result.model_dump() == {
            "front_text": "Radio", "back_text": "Radio",
            "front_lang": "ru", "back_lang": "en",
        }
