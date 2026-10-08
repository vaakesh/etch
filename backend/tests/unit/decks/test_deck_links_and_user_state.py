from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.decks.schemas import (
    DeckCardResponse,
    InternalDeckCard,
    InternalUserDeck,
    ReorderCards,
)
from app.decks.errors import CannotFavouriteUnsavedDeckError
from app.decks.service import UserDeckService
from app.redis.invalidation import CacheInvalidator
from app.errors import RequestValueError
from tests.unit.factories import make_deck, make_deck_card, make_user_deck


@pytest.fixture
def favourite_context():
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.deck_repo.get_by_uuid = AsyncMock(return_value=make_deck(user_id=7))
    uow.user_deck_repo.get_by_user_id_and_deck_id = AsyncMock()
    invalidator = create_autospec(CacheInvalidator, instance=True)
    return UserDeckService(lambda: uow, AsyncMock(), invalidator), uow, invalidator


class TestSetFavouriteDeck:
    @pytest.mark.parametrize("value", [True, False])
    async def test_repeated_value_does_not_write_or_invalidate(self, favourite_context, value):
        service, uow, cache = favourite_context
        state = make_user_deck(is_saved=True, is_favourite=value)
        uow.user_deck_repo.get_by_user_id_and_deck_id.return_value = state

        result = await service.set_favourite_deck(
            user_id=42,
            deck_uuid=UUID("0198ad01-b200-7000-8000-000000000200"),
            value=value,
        )

        assert result.is_favourite is value
        assert result.is_saved is True
        uow.commit.assert_not_awaited()
        cache.invalidate.assert_not_awaited()

    @pytest.mark.parametrize("state_exists", [True, False])
    async def test_rejects_unsaved_foreign_deck(self, favourite_context, state_exists):
        service, uow, cache = favourite_context
        state = make_user_deck(is_saved=False) if state_exists else None
        uow.user_deck_repo.get_by_user_id_and_deck_id.return_value = state

        with pytest.raises(CannotFavouriteUnsavedDeckError):
            await service.set_favourite_deck(
                user_id=42,
                deck_uuid=UUID("0198ad01-b200-7000-8000-000000000200"),
                value=True,
            )

        uow.commit.assert_not_awaited()
        cache.invalidate.assert_not_awaited()


class TestDeckCardIdentifiers:
    @pytest.mark.parametrize("field", ["id", "deck_id", "card_id"])
    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_nonpositive_id(self, field, value):
        link = make_deck_card(**{field: value})

        with pytest.raises(ValidationError) as error:
            InternalDeckCard.model_validate(link)

        assert error.value.errors()[0]["loc"] == (field,)

    @pytest.mark.parametrize("schema", [InternalDeckCard, DeckCardResponse])
    def test_rejects_uuid_other_than_v7(self, schema):
        link = make_deck_card(uuid=UUID("00000000-0000-4000-8000-000000000001"))

        with pytest.raises(ValidationError) as error:
            schema.model_validate(link)

        assert error.value.errors()[0]["loc"] == ("uuid",)
        assert error.value.errors()[0]["type"] == "uuid_version"

    @pytest.mark.parametrize("schema", [InternalDeckCard, DeckCardResponse])
    @pytest.mark.parametrize("position", [0, 5001])
    def test_rejects_position_outside_deck(self, schema, position):
        link = make_deck_card(position=position)

        with pytest.raises(ValidationError) as error:
            schema.model_validate(link)

        assert error.value.errors()[0]["loc"] == ("position",)

    @pytest.mark.parametrize("position", [0, 5001])
    def test_reorder_rejects_position_outside_deck(self, position):
        with pytest.raises(ValidationError) as error:
            ReorderCards(card_uuid=UUID("0198ad01-b200-7000-8000-000000000100"), to_position=position)

        assert error.value.errors()[0]["loc"] == ("to_position",)


class TestDeckCardDates:
    def test_accepts_equal_created_and_updated_dates(self):
        timestamp = datetime(2020, 1, 1, 12, tzinfo=UTC)
        link = make_deck_card(created_at=timestamp, updated_at=timestamp)

        result = InternalDeckCard.model_validate(link)

        assert result.updated_at == timestamp

    def test_rejects_update_before_creation(self):
        link = make_deck_card(
            created_at=datetime(2020, 1, 1, 12, tzinfo=UTC),
            updated_at=datetime(2020, 1, 1, 11, tzinfo=UTC),
        )

        with pytest.raises(RequestValueError) as error:
            InternalDeckCard.model_validate(link)

        assert error.value.failed_field == "updated_at"


class TestUserDeckState:
    @pytest.mark.parametrize("field", ["user_id", "deck_id"])
    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_nonpositive_id(self, field, value):
        state = make_user_deck(**{field: value})

        with pytest.raises(ValidationError) as error:
            InternalUserDeck.model_validate(state)

        assert error.value.errors()[0]["loc"] == (field,)

    @pytest.mark.parametrize("field", ["sessions_count", "correct_count", "wrong_count"])
    def test_rejects_negative_counter(self, field):
        state = make_user_deck(**{field: -1})

        with pytest.raises(ValidationError) as error:
            InternalUserDeck.model_validate(state)

        assert error.value.errors()[0]["loc"] == (field,)

    @pytest.mark.parametrize("field", ["is_saved", "is_favourite"])
    @pytest.mark.parametrize("value", [0, 1, "true", "false"])
    def test_rejects_non_boolean_flag(self, field, value):
        state = make_user_deck(**{field: value})

        with pytest.raises(ValidationError) as error:
            InternalUserDeck.model_validate(state)

        assert error.value.errors()[0]["loc"] == (field,)

    def test_accepts_creation_without_study(self):
        state = make_user_deck(last_studied_at=None, sessions_count=0)

        result = InternalUserDeck.model_validate(state)

        assert result.last_studied_at is None
        assert result.added_at == state.added_at

    @pytest.mark.parametrize("field", ["correct_count", "wrong_count"])
    def test_rejects_answers_without_completed_sessions(self, field):
        state = make_user_deck(sessions_count=0, **{field: 1})

        with pytest.raises(RequestValueError) as error:
            InternalUserDeck.model_validate(state)

        assert error.value.failed_field == field

    @pytest.mark.parametrize(("sessions_count", "last_studied_at"), [
        (0, datetime(2020, 1, 2, tzinfo=UTC)),
        (1, None),
    ])
    def test_rejects_study_date_inconsistent_with_sessions(self, sessions_count, last_studied_at):
        state = make_user_deck(
            sessions_count=sessions_count, last_studied_at=last_studied_at,
        )

        with pytest.raises(RequestValueError) as error:
            InternalUserDeck.model_validate(state)

        assert error.value.failed_field == "last_studied_at"

    @pytest.mark.parametrize("last_studied_at", [
        datetime(2020, 1, 1, tzinfo=UTC),
        datetime(2020, 1, 2),
    ])
    def test_rejects_earlier_or_timezone_incompatible_study_date(self, last_studied_at):
        state = make_user_deck(
            sessions_count=1, last_studied_at=last_studied_at,
            added_at=datetime(2020, 1, 2, tzinfo=UTC),
        )

        with pytest.raises(RequestValueError) as error:
            InternalUserDeck.model_validate(state)

        assert error.value.failed_field == "last_studied_at"

    @pytest.mark.parametrize("last_studied_at", [
        datetime(2020, 1, 1, tzinfo=UTC),
        datetime(2020, 1, 2, tzinfo=UTC),
    ])
    @pytest.mark.parametrize(("correct_count", "wrong_count"), [(0, 0), (3, 2)])
    def test_accepts_completed_sessions_with_valid_study_date(
        self, last_studied_at, correct_count, wrong_count,
    ):
        state = make_user_deck(
            sessions_count=1, correct_count=correct_count, wrong_count=wrong_count,
            last_studied_at=last_studied_at,
            added_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

        result = InternalUserDeck.model_validate(state)

        assert result.last_studied_at == last_studied_at
        assert result.correct_count == correct_count
        assert result.wrong_count == wrong_count
