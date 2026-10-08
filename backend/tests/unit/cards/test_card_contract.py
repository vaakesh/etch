from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.cards.schemas import CardResponse, InternalCard, LoadedCardResponse, UpdateCardRequest
from app.cards.repository import CardRepository
from app.cards.service import CardService
from app.decks.schemas import ReorderCards
from app.errors import RequestValueError
from app.redis.service import RedisCacheService
from app.redis.invalidation import CacheInvalidator
from tests.unit.factories import make_card

CARD_UUID = UUID("0198ad01-b200-7000-8000-000000000100")


class TestInternalCard:
    @pytest.mark.parametrize("field", ["id", "user_id"])
    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_nonpositive_id(self, field, value):
        card = make_card(uuid=CARD_UUID, **{field: value})

        with pytest.raises(ValidationError) as error:
            InternalCard.model_validate(card)

        assert error.value.errors()[0]["loc"] == (field,)

    def test_preserves_owner_in_internal_dto(self):
        card = make_card(uuid=CARD_UUID, user_id=42)

        result = InternalCard.from_entity(card)

        assert result.user_id == 42

    @pytest.mark.parametrize("schema", [InternalCard, CardResponse, LoadedCardResponse])
    def test_rejects_uuid_other_than_v7(self, schema):
        card = make_card(uuid=UUID("00000000-0000-4000-8000-000000000001"))
        payload = {**vars(card), "position": 1}

        with pytest.raises(ValidationError) as error:
            schema.model_validate(payload)

        assert error.value.errors()[0]["loc"] == ("uuid",)
        assert error.value.errors()[0]["type"] == "uuid_version"

    @pytest.mark.parametrize("updated_at", [
        datetime(2020, 1, 1, tzinfo=UTC), datetime(2020, 1, 2),
    ])
    def test_rejects_earlier_or_incompatible_update_date(self, updated_at):
        card = make_card(
            uuid=CARD_UUID, created_at=datetime(2020, 1, 2, tzinfo=UTC),
            updated_at=updated_at,
        )

        with pytest.raises(RequestValueError) as error:
            InternalCard.model_validate(card)

        assert error.value.failed_field == "updated_at"

    def test_accepts_equal_dates(self):
        date = datetime(2020, 1, 1, tzinfo=UTC)
        card = make_card(uuid=CARD_UUID, created_at=date, updated_at=date)

        result = InternalCard.model_validate(card)

        assert result.updated_at == date


class TestCardReferences:
    @pytest.mark.parametrize("position", [0, 5001])
    def test_import_response_rejects_position_outside_deck(self, position):
        with pytest.raises(ValidationError) as error:
            LoadedCardResponse(uuid=CARD_UUID, position=position)

        assert error.value.errors()[0]["loc"] == ("position",)

    def test_reorder_rejects_uuid_other_than_v7(self):
        with pytest.raises(ValidationError) as error:
            ReorderCards(card_uuid="00000000-0000-4000-8000-000000000001", to_position=1)

        assert error.value.errors()[0]["type"] == "uuid_version"

    @pytest.mark.parametrize(("method", "path", "field"), [
        ("PATCH", "/cards/00000000-0000-4000-8000-000000000001", "card_uuid"),
        ("DELETE", "/cards/00000000-0000-4000-8000-000000000001", "card_uuid"),
        ("GET", "/decks/00000000-0000-4000-8000-000000000001", "deck_uuid"),
        ("GET", "/users/00000000-0000-4000-8000-000000000001/decks", "user_uuid"),
    ])
    async def test_routes_reject_uuid_other_than_v7(self, client, method, path, field):
        response = await client.request(method, path, json={})

        assert response.status_code == 422
        assert response.json() == {
            "code": "VALIDATION_ERROR", "message": "Validation error",
            "details": [{"type": "uuid_version", "loc": ["path", field],
                         "msg": "UUID version 7 expected",
                         "input": "00000000-0000-4000-8000-000000000001",
                         "ctx": {"expected_version": 7}}],
        }


class TestUpdateCardRequest:
    @pytest.mark.parametrize("field", ["front_text", "back_text", "front_lang", "back_lang"])
    def test_rejects_explicit_null(self, field):
        with pytest.raises(RequestValueError) as error:
            UpdateCardRequest(**{field: None})

        assert error.value.failed_field == field

    def test_omitted_fields_are_excluded(self):
        result = UpdateCardRequest(front_text=" Word ")

        assert result.model_dump(exclude_unset=True) == {"front_text": "Word"}

    @pytest.mark.parametrize("field", ["front_text", "back_text", "front_lang", "back_lang"])
    def test_schema_does_not_allow_null(self, field):
        schema = UpdateCardRequest.model_json_schema()
        prop = schema["properties"][field]

        assert "anyOf" not in prop
        assert schema["$defs"][prop["$ref"].split("/")[-1]]["type"] == "string"
        assert field not in schema.get("required", [])


class TestUpdateCard:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", [
        {}, {"front_text": " привет ", "back_text": "hello", "front_lang": " RU ", "back_lang": "EN"},
    ])
    async def test_preserves_date_without_writing_when_content_is_unchanged(self, payload):
        card = make_card(uuid=CARD_UUID)
        uow = MagicMock()
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock(return_value=False)
        uow.card_repo = create_autospec(CardRepository, instance=True)
        uow.card_repo.get_by_uuid.return_value = card
        uow.commit = AsyncMock()
        cache = create_autospec(RedisCacheService, instance=True)
        invalidator = create_autospec(CacheInvalidator, instance=True)
        service = CardService(
            uow_factory=lambda: uow, cache_service=cache, cache_invalidator=invalidator,
        )

        result = await service.update_card(CARD_UUID, card.user_id, UpdateCardRequest(**payload))

        assert result.model_dump() == {
            "id": 100,
            "uuid": CARD_UUID,
            "user_id": 42,
            "front_text": "привет",
            "back_text": "hello",
            "front_lang": "ru",
            "back_lang": "en",
            "created_at": datetime(2026, 8, 15, 14, tzinfo=UTC),
            "updated_at": datetime(2026, 8, 15, 15, tzinfo=UTC),
        }
        uow.commit.assert_not_awaited()
        uow.card_repo.refresh.assert_not_awaited()
        invalidator.invalidate.assert_not_awaited()
