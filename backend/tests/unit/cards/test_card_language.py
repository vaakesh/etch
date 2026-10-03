import pytest
from pydantic import TypeAdapter, ValidationError

from app.cards.schemas import CreateCardRequest, UpdateCardRequest
from app.common.types import CardLang


class TestCardLang:
    @pytest.mark.parametrize(("value", "expected"), [
        ("ru", "ru"), ("eng", "eng"), (" EN ", "en"),
        ("\u00a0DeU\u2003", "deu"), ("zz", "zz"),
    ])
    def test_normalizes_language_code(self, value, expected):
        adapter = TypeAdapter(CardLang)

        result = adapter.validate_python(value)

        assert result == expected

    @pytest.mark.parametrize("value", [
        "", "e", "engl", "12", "аб", "e1", "e-n", "e n", "en-US", "éé", None,
    ])
    def test_rejects_invalid_language_code(self, value):
        adapter = TypeAdapter(CardLang)

        with pytest.raises(ValidationError):
            adapter.validate_python(value)


class TestCardLanguageRequests:
    def test_defaults_to_russian_and_english(self):
        result = CreateCardRequest(front_text="Слово", back_text="Word")

        assert result.front_lang == "ru"
        assert result.back_lang == "en"

    def test_accepts_same_language_on_both_sides(self):
        result = CreateCardRequest(
            front_text="Word", back_text="Definition", front_lang=" EN ", back_lang="EN",
        )

        assert result.front_lang == "en"
        assert result.back_lang == "en"

    @pytest.mark.parametrize("field", ["front_lang", "back_lang"])
    @pytest.mark.parametrize(("schema", "location_suffix"), [
        (CreateCardRequest, ()), (UpdateCardRequest, ("constrained-str",)),
    ])
    def test_rejects_invalid_language_on_either_side(self, field, schema, location_suffix):
        payload = {"front_text": "Word", "back_text": "Слово", field: "12"}

        with pytest.raises(ValidationError) as error:
            schema(**payload)

        assert error.value.errors()[0]["loc"] == (field, *location_suffix)
        assert error.value.errors()[0]["type"] == "string_pattern_mismatch"
