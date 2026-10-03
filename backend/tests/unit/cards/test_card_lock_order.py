from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from app.cards.errors import CardNotFoundError
from app.cards.repository import CardRepository
from app.cards.service import CardService
from app.decks.repository import DeckCardRepository, DeckRepository
from app.decks.service import DeckService
from app.redis.service import RedisCacheService
from tests.unit.factories import make_card, make_deck, make_deck_card


@pytest.fixture
def lock_context():
    card = make_card()
    deck = make_deck(words_count=2)
    deck.mark_content_changed = MagicMock()
    link = make_deck_card(position=1)
    locks = []
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.flush = AsyncMock()
    uow.rollback = AsyncMock()
    uow.card_repo = create_autospec(CardRepository, instance=True)
    uow.deck_repo = create_autospec(DeckRepository, instance=True)
    uow.deck_card_repo = create_autospec(DeckCardRepository, instance=True)
    uow.deck_card_repo.get_all_deck_ids_by_card_ids.return_value = [200]
    uow.deck_card_repo.get_max_position.return_value = 2
    cache = create_autospec(RedisCacheService, instance=True)

    async def get_card(card_uuid, for_update=False):
        if for_update:
            locks.append("card")
        return card

    async def get_owned_deck(**kwargs):
        if kwargs["for_update"]:
            locks.append("deck")
        return deck

    async def get_related_decks(card_ids, for_update=False):
        if for_update:
            locks.append("deck")
        return [200]

    def add_link(entity):
        entity.id = 300
        entity.uuid = link.uuid
        entity.created_at = link.created_at
        entity.updated_at = link.updated_at

    uow.card_repo.get_by_uuid.side_effect = get_card
    uow.deck_repo.get_owned_by_uuid.side_effect = get_owned_deck
    uow.deck_card_repo.get_all_deck_ids_by_card_ids.side_effect = get_related_decks
    uow.deck_card_repo.add.side_effect = add_link
    return uow, cache, card, deck, link, locks


class TestAddCardToDeck:
    async def test_locks_deck_before_card_and_adds_link(self, lock_context):
        uow, cache, card, deck, link, locks = lock_context
        uow.deck_card_repo.get_by_deck_id_and_card_id.return_value = None
        service = DeckService(uow_factory=lambda: uow, cache_service=cache)

        result = await service.add_card_to_deck(
            user_id=42, deck_uuid=deck.uuid, card_uuid=card.uuid,
        )

        assert locks == ["deck", "card"]
        assert result.model_dump() == {
            "id": 300,
            "uuid": link.uuid,
            "deck_id": 200,
            "card_id": 100,
            "position": 3,
            "created_at": link.created_at,
            "updated_at": link.updated_at,
        }
        assert deck.words_count == 3
        uow.commit.assert_awaited_once()


class TestRemoveCardFromDeck:
    async def test_locks_deck_before_card_and_removes_link(self, lock_context):
        uow, cache, card, deck, link, locks = lock_context
        uow.deck_card_repo.get_by_deck_id_and_card_id.return_value = link
        service = DeckService(uow_factory=lambda: uow, cache_service=cache)

        await service.remove_card_from_deck(
            user_id=42, deck_uuid=deck.uuid, card_uuid=card.uuid,
        )

        assert locks == ["deck", "card"]
        assert deck.words_count == 1
        uow.deck_card_repo.delete.assert_awaited_once_with(link)
        uow.deck_card_repo.update_deck_cards_positions_after_deleting.assert_awaited_once_with(
            deck_id=200, deleted_position=1,
        )
        uow.commit.assert_awaited_once()


class TestDeleteCard:
    async def test_locks_decks_before_card_and_recounts_affected_decks(self, lock_context):
        uow, cache, card, deck, link, locks = lock_context
        service = CardService(uow_factory=lambda: uow, cache_service=cache)

        await service.delete_card(user_id=42, card_uuid=card.uuid)

        assert locks == ["deck", "card"]
        uow.card_repo.delete.assert_awaited_once_with(card)
        uow.deck_card_repo.normalize_positions.assert_awaited_once_with(deck_ids=[200])
        uow.deck_card_repo.update_cards_count.assert_awaited_once_with(deck_ids=[200])
        uow.commit.assert_awaited_once()
        uow.rollback.assert_not_awaited()
        cache.invalidate_decks.assert_awaited_once_with(deck_ids=[200])

    @pytest.mark.parametrize("initial_deck_ids", [[200], []])
    async def test_releases_locks_and_retries_when_card_gains_a_deck(
        self, lock_context, initial_deck_ids,
    ):
        uow, cache, card, deck, link, locks = lock_context
        uow.deck_card_repo.get_all_deck_ids_by_card_ids.side_effect = [
            initial_deck_ids, [200, 201], [200, 201], [200, 201],
        ]
        service = CardService(uow_factory=lambda: uow, cache_service=cache)

        async def rollback():
            uow.card_repo.delete.assert_not_awaited()
            uow.commit.assert_not_awaited()
            cache.invalidate_decks.assert_not_awaited()

        uow.rollback.side_effect = rollback

        await service.delete_card(user_id=42, card_uuid=card.uuid)

        uow.rollback.assert_awaited_once()
        uow.card_repo.delete.assert_awaited_once_with(card)
        uow.deck_card_repo.normalize_positions.assert_awaited_once_with(deck_ids=[200, 201])
        uow.deck_card_repo.update_cards_count.assert_awaited_once_with(deck_ids=[200, 201])
        uow.commit.assert_awaited_once()
        cache.invalidate_decks.assert_awaited_once_with(deck_ids=[200, 201])

    async def test_does_not_retry_when_card_loses_a_deck(self, lock_context):
        uow, cache, card, deck, link, locks = lock_context
        uow.deck_card_repo.get_all_deck_ids_by_card_ids.side_effect = [
            [200, 201], [200],
        ]
        service = CardService(uow_factory=lambda: uow, cache_service=cache)

        await service.delete_card(user_id=42, card_uuid=card.uuid)

        uow.rollback.assert_not_awaited()
        uow.card_repo.delete.assert_awaited_once_with(card)
        uow.deck_card_repo.update_cards_count.assert_awaited_once_with(deck_ids=[200, 201])

    async def test_returns_not_found_without_locking_decks_for_another_owner(
        self, lock_context,
    ):
        uow, cache, card, deck, link, locks = lock_context
        card.user_id = 7
        service = CardService(uow_factory=lambda: uow, cache_service=cache)

        with pytest.raises(CardNotFoundError):
            await service.delete_card(user_id=42, card_uuid=card.uuid)

        assert locks == []
        uow.deck_card_repo.get_all_deck_ids_by_card_ids.assert_not_awaited()
        uow.card_repo.delete.assert_not_awaited()
        uow.commit.assert_not_awaited()

    async def test_returns_not_found_when_card_disappears_before_its_lock(
        self, lock_context,
    ):
        uow, cache, card, deck, link, locks = lock_context
        uow.card_repo.get_by_uuid.side_effect = [card, None]
        service = CardService(uow_factory=lambda: uow, cache_service=cache)

        with pytest.raises(CardNotFoundError):
            await service.delete_card(user_id=42, card_uuid=card.uuid)

        uow.card_repo.delete.assert_not_awaited()
        uow.commit.assert_not_awaited()

    async def test_returns_not_found_when_owner_changes_before_card_lock(
        self, lock_context,
    ):
        uow, cache, card, deck, link, locks = lock_context
        uow.card_repo.get_by_uuid.side_effect = [card, make_card(user_id=7)]
        service = CardService(uow_factory=lambda: uow, cache_service=cache)

        with pytest.raises(CardNotFoundError):
            await service.delete_card(user_id=42, card_uuid=card.uuid)

        uow.card_repo.delete.assert_not_awaited()
        uow.commit.assert_not_awaited()
        assert cache.mock_calls == []
