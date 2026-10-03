from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.decks.schemas import CreateDeckRequest, DeckResponse, InternalDeck, UpdateDeckRequest
from app.errors import RequestValueError
from tests.unit.factories import make_deck


class TestDeckVisibility:
    @pytest.mark.parametrize('schema', [CreateDeckRequest, UpdateDeckRequest, InternalDeck, DeckResponse])
    @pytest.mark.parametrize('value', [True, False])
    def test_accepts_boolean(self, schema, value):
        payload = vars(make_deck(is_public=value))

        result = schema.model_validate(payload)

        assert result.is_public is value

    @pytest.mark.parametrize('schema, expected_errors', [
        (CreateDeckRequest, [(('is_public',), 'bool_type')]),
        (UpdateDeckRequest, [(('is_public', 'bool'), 'bool_type'), (('is_public', 'none'), 'none_required')]),
        (InternalDeck, [(('is_public',), 'bool_type')]),
        (DeckResponse, [(('is_public',), 'bool_type')]),
    ])
    @pytest.mark.parametrize('value', ['true', 'false', '1', '0', 1, 0, 1.0, 0.0])
    def test_rejects_non_boolean(self, schema, expected_errors, value):
        payload = vars(make_deck(is_public=value))

        with pytest.raises(ValidationError) as error:
            schema.model_validate(payload)

        assert [(item['loc'], item['type']) for item in error.value.errors()] == expected_errors

    def test_creation_defaults_to_private(self):
        result = CreateDeckRequest(title='English')

        assert result.is_public is False

    def test_omitted_visibility_does_not_update_value(self):
        result = UpdateDeckRequest(title='English')

        assert result.model_dump(exclude_unset=True) == {'title': 'English'}

    def test_explicit_false_is_included_in_update(self):
        result = UpdateDeckRequest(is_public=False)

        assert result.model_dump(exclude_unset=True) == {'is_public': False}

    def test_update_rejects_explicit_null(self):
        with pytest.raises(RequestValueError) as error:
            UpdateDeckRequest(is_public=None)

        assert error.value.failed_field == 'is_public'
        assert str(error.value) == 'is_public value cannot be null'

    def test_create_rejects_explicit_null(self):
        with pytest.raises(ValidationError) as error:
            CreateDeckRequest(title='English', is_public=None)

        assert error.value.errors()[0]['loc'] == ('is_public',)
        assert error.value.errors()[0]['type'] == 'bool_type'

    def test_update_schema_only_advertises_boolean(self):
        schema = UpdateDeckRequest.model_json_schema()

        assert schema['properties']['is_public']['type'] == 'boolean'
        assert 'anyOf' not in schema['properties']['is_public']


class TestDeckDates:
    @pytest.mark.parametrize('hour', [12, 13])
    def test_accepts_equal_or_later_update(self, hour):
        deck = make_deck(
            created_at=datetime(2020, 1, 1, 12, tzinfo=UTC),
            updated_at=datetime(2020, 1, 1, hour, tzinfo=UTC),
        )

        result = InternalDeck.model_validate(deck)

        assert result.updated_at == datetime(2020, 1, 1, hour, tzinfo=UTC)

    def test_rejects_update_before_creation(self):
        deck = make_deck(
            created_at=datetime(2020, 1, 1, 12, tzinfo=UTC),
            updated_at=datetime(2020, 1, 1, 11, tzinfo=UTC),
        )

        with pytest.raises(RequestValueError) as error:
            InternalDeck.model_validate(deck)

        assert error.value.failed_field == 'updated_at'
        assert str(error.value) == 'updated_at must be greater than or equal to created_at'

    @pytest.mark.parametrize('created_at, updated_at', [
        (datetime(2020, 1, 1, 12), datetime(2020, 1, 1, 13, tzinfo=UTC)),
        (datetime(2020, 1, 1, 12, tzinfo=UTC), datetime(2020, 1, 1, 13)),
    ])
    def test_rejects_incompatible_timezones(self, created_at, updated_at):
        deck = make_deck(created_at=created_at, updated_at=updated_at)

        with pytest.raises(RequestValueError) as error:
            InternalDeck.model_validate(deck)

        assert error.value.failed_field == 'updated_at'
        assert str(error.value) == 'Dates must have compatible timezone information'

    def test_keeps_naive_dates_supported(self):
        deck = make_deck(
            created_at=datetime(2020, 1, 1, 12),
            updated_at=datetime(2020, 1, 1, 13),
        )

        result = InternalDeck.model_validate(deck)

        assert result.updated_at == datetime(2020, 1, 1, 13)
