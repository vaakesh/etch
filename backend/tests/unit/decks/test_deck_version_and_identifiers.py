from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.decks.models import Deck
from app.decks.schemas import DeckResponse, InternalDeck, UpdateDeckRequest
from app.decks.service import DeckService
from app.redis.service import RedisCacheService
from app.redis.invalidation import BumpGeneration, CacheInvalidator, DelKey
from app.users.models import User
from tests.unit.factories import make_deck


@pytest.fixture
def deck():
    data = vars(make_deck()).copy()
    data.pop('owner_uuid')
    data.pop('owner_username')
    data.pop('user')
    entity = Deck(**data)
    entity.user = User(id=42, uuid=UUID('0198ad01-b200-7000-8000-000000000042'), username='test-user')
    return entity


@pytest.fixture
def service_context(deck):
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.deck_repo.get_owned_by_uuid = AsyncMock(return_value=deck)
    uow.user_deck_repo.get_library_user_ids_by_deck_ids = AsyncMock(return_value=[42])
    cache = create_autospec(RedisCacheService, instance=True)
    invalidator = create_autospec(CacheInvalidator, instance=True)
    return DeckService(lambda: uow, cache, invalidator), uow


class TestUpdateDeckVersion:
    @pytest.mark.parametrize('payload', [
        {'title': 'New title'}, {'description': 'New description'},
        {'description': None}, {'title': 'New title', 'description': 'New description'},
    ])
    async def test_increments_once_when_text_changes(self, service_context, deck, payload, monkeypatch):
        service, uow = service_context
        now = datetime(2026, 9, 1, tzinfo=UTC)
        monkeypatch.setattr('app.decks.models.utcnow', lambda: now)

        result = await service.update_deck(42, deck.uuid, UpdateDeckRequest(**payload))

        assert result.version == 2
        assert result.updated_at == now
        uow.commit.assert_awaited_once()
        service.cache_invalidator.invalidate.assert_awaited_once()
        assert {
            op for group in service.cache_invalidator.invalidate.await_args.args for op in group
        } == {
            DelKey("deck:200"),
            BumpGeneration("library:42:decks:generation"),
        }

    @pytest.mark.parametrize('payload', [
        {}, {'title': '  Test deck  '}, {'description': 'Test deck description'}, {'is_public': True},
    ])
    async def test_preserves_version_and_date_without_content_change(self, service_context, deck, payload):
        service, uow = service_context
        previous_date = deck.updated_at

        result = await service.update_deck(42, deck.uuid, UpdateDeckRequest(**payload))

        assert result.version == 1
        assert result.updated_at == previous_date
        uow.commit.assert_awaited_once()
        service.cache_invalidator.invalidate.assert_not_awaited()


class TestReorderDeckVersion:
    async def test_changes_position_without_changing_deck_version_or_date(self, service_context, deck):
        service, uow = service_context
        previous_date = deck.updated_at
        card = SimpleNamespace(id=100, user_id=42, uuid=UUID('0198ad01-b200-7000-8000-000000000100'))
        link = SimpleNamespace(position=1)
        uow.card_repo.get_by_uuid = AsyncMock(return_value=card)
        uow.deck_card_repo.get_by_deck_id_and_card_id = AsyncMock(return_value=link)
        uow.deck_card_repo.reorder_cards = AsyncMock()

        await service.reorder_cards(42, deck.uuid, card.uuid, 2)

        assert link.position == 2
        assert deck.version == 1
        assert deck.updated_at == previous_date
        uow.commit.assert_awaited_once()
        service.cache_invalidator.invalidate.assert_awaited_once()
        assert {
            op for group in service.cache_invalidator.invalidate.await_args.args for op in group
        } == {DelKey("deck:200:card-ids")}


class TestDeckIdentifiers:
    @pytest.mark.parametrize('field', ['id', 'user_id'])
    @pytest.mark.parametrize('value', [0, -1])
    def test_rejects_nonpositive_id(self, field, value):
        payload = make_deck(**{field: value})

        with pytest.raises(ValidationError) as error:
            InternalDeck.model_validate(payload)

        assert error.value.errors()[0]['loc'] == (field,)
        assert error.value.errors()[0]['type'] == 'greater_than_equal'

    @pytest.mark.parametrize('schema', [InternalDeck, DeckResponse])
    @pytest.mark.parametrize('field', ['uuid', 'owner_uuid'])
    def test_rejects_uuid_other_than_v7(self, schema, field):
        payload = make_deck()
        setattr(payload, field, UUID('00000000-0000-4000-8000-000000000001'))

        with pytest.raises(ValidationError) as error:
            schema.model_validate(payload)

        assert error.value.errors()[0]['loc'] == (field,)
        assert error.value.errors()[0]['type'] == 'uuid_version'
