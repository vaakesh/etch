import pytest
from pydantic import TypeAdapter, ValidationError

from app.common.types import DeckDescription, DeckTitle
from app.decks.schemas import CreateDeckRequest, UpdateDeckRequest
from app.errors import RequestValueError


class TestDeckTitle:
    @pytest.mark.parametrize(('value', 'expected'), [
        ('English A1', 'English A1'),
        ('  Английский A1  ', 'Английский A1'),
        ('\u00a0日本語 🙂\u2003', '日本語 🙂'),
        ('A  B', 'A  B'), ('ABC', 'ABC'), ('a' * 50, 'a' * 50),
    ])
    def test_accepts_title_and_trims_edges(self, value, expected):
        adapter = TypeAdapter(DeckTitle)

        result = adapter.validate_python(value)

        assert result == expected

    @pytest.mark.parametrize('value', ['', '   ', 'ab', 'a' * 51, 'A\tB', 'A\nB', 'A\rB', 'A\vB', 'A\fB', 'A\x85B', 'A\u2028B', 'A\u2029B'])
    def test_rejects_invalid_length_or_line_breaks(self, value):
        adapter = TypeAdapter(DeckTitle)

        with pytest.raises(ValidationError):
            adapter.validate_python(value)


class TestDeckDescription:
    @pytest.mark.parametrize(('value', 'expected'), [
        (None, None), ('', None), (' \t\n\u00a0\u2003', None),
        ('Description', 'Description'),
        ('  First\n\tSecond  ', 'First\n\tSecond'),
        ('a' * 3000, 'a' * 3000),
    ])
    def test_normalizes_description_and_preserves_formatting(self, value, expected):
        adapter = TypeAdapter(DeckDescription)

        result = adapter.validate_python(value)

        assert result == expected

    def test_rejects_description_over_limit(self):
        adapter = TypeAdapter(DeckDescription)

        with pytest.raises(ValidationError):
            adapter.validate_python('a' * 3001)


class TestUpdateDeckRequest:
    def test_omitted_title_is_excluded_from_update(self):
        payload = UpdateDeckRequest()

        result = payload.model_dump(exclude_unset=True)

        assert result == {}

    def test_rejects_explicit_null_title(self):
        with pytest.raises(RequestValueError) as error:
            UpdateDeckRequest(title=None)

        assert error.value.failed_field == "title"

    def test_title_schema_is_optional_nonnullable_string(self):
        schema = UpdateDeckRequest.model_json_schema()

        title = schema["properties"]["title"]

        assert title["$ref"] == "#/$defs/DeckTitle"
        assert schema["$defs"]["DeckTitle"]["type"] == "string"
        assert "anyOf" not in title
        assert "title" not in schema.get("required", [])

    def test_omitted_description_is_excluded_from_update(self):
        payload = UpdateDeckRequest(title='English')

        result = payload.model_dump(exclude_unset=True)

        assert result == {'title': 'English'}

    @pytest.mark.parametrize('value', [None, '', ' \t\n '])
    def test_explicit_empty_description_clears_value(self, value):
        payload = UpdateDeckRequest(description=value)

        result = payload.model_dump(exclude_unset=True)

        assert result == {'description': None}


class TestCreateDeckRequest:
    def test_normalizes_text_for_storage(self):
        payload = {'title': '  Английский A1  ', 'description': ' \n '}

        result = CreateDeckRequest(**payload)

        assert result.model_dump() == {
            'title': 'Английский A1', 'description': None, 'is_public': False,
        }
