from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.cards.models import Card
from app.decks.errors import DeckNotFoundError
from app.decks.models import Deck, DeckCard
from app.decks.service import DeckArchiver
from app.users.service import UserService


@pytest.fixture
def source_deck():
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    card = Card(
        id=20, user_id=7, front_text="hello", back_text="привет",
        front_lang="en", back_lang="ru", created_at=timestamp, updated_at=timestamp,
    )
    return Deck(
        id=10, user_id=7, title="Words", description="Basic words",
        words_count=1, is_public=True, saves_count=99, version=3,
        created_at=timestamp, updated_at=timestamp,
        card_links=[DeckCard(
            deck_id=10, card_id=20, card=card, position=1,
            created_at=timestamp, updated_at=timestamp,
        )],
    )


@pytest.fixture
def uow(source_deck):
    unit = MagicMock()
    unit.__aenter__ = AsyncMock(return_value=unit)
    unit.__aexit__ = AsyncMock(return_value=False)
    unit.commit = AsyncMock()
    unit.flush = AsyncMock()
    unit.deck_repo.get_decks_with_all_cards = AsyncMock(return_value=[source_deck])
    unit.deck_repo.has_archivable_user_decks = AsyncMock(return_value=True)
    unit.deck_repo.reassign_user_decks = AsyncMock(return_value=[(8, True), (9, True)])
    unit.training_session_repo.has_by_deck_id = AsyncMock(return_value=False)
    unit.training_session_repo.reassign_deck = AsyncMock(return_value=[])
    unit.deck_repo.add.side_effect = lambda deck: setattr(deck, "id", 100)
    unit.card_repo.add_all.side_effect = lambda cards: setattr(cards[0], "id", 200)
    return unit


class TestArchive:
    async def test_copies_content_and_moves_saves_to_archive_owner(self, uow, source_deck):
        archiver = DeckArchiver()

        affected = await archiver.archive(uow=uow, deck=source_deck)

        archived = uow.deck_repo.add.call_args.kwargs["deck"]
        copied_card = uow.card_repo.add_all.call_args.kwargs["cards"][0]
        copied_link = uow.deck_card_repo.add_all.call_args.kwargs["deck_cards"][0]
        assert affected == [8, 9]
        assert (archived.user_id, archived.source_deck_id, archived.saves_count) == (1, 10, 2)
        assert (archived.title, archived.description, archived.words_count, archived.version) == (
            "Words", "Basic words", 1, 3,
        )
        assert (copied_card.user_id, copied_card.front_text, copied_card.back_text) == (1, "hello", "привет")
        assert (copied_card.front_lang, copied_card.back_lang) == ("en", "ru")
        assert (copied_link.deck_id, copied_link.card_id, copied_link.position) == (100, 200, 1)
        assert copied_card is not source_deck.card_links[0].card
        assert source_deck.card_links[0].card.user_id == 7
        assert source_deck.saves_count == 0
        uow.deck_repo.reassign_user_decks.assert_awaited_once_with(
            from_deck_id=10, to_deck_id=100, exclude_user_id=7,
        )
        uow.commit.assert_not_awaited()

    async def test_does_not_create_copy_without_saves_or_history(self, uow, source_deck):
        uow.deck_repo.has_archivable_user_decks.return_value = False

        affected = await DeckArchiver().archive(uow=uow, deck=source_deck)

        assert affected == []
        uow.deck_repo.add.assert_not_called()
        uow.card_repo.add_all.assert_not_called()
        uow.deck_repo.has_archivable_user_decks.assert_awaited_once_with(deck_id=10, exclude_user_id=7)

    async def test_skips_archive_owned_decks(self, uow, source_deck):
        source_deck.user_id = 1

        affected = await DeckArchiver().archive(uow=uow, deck=source_deck)

        assert affected == []
        uow.deck_repo.add.assert_not_called()

    async def test_raises_when_source_was_deleted(self, uow, source_deck):
        uow.deck_repo.get_decks_with_all_cards.return_value = []

        with pytest.raises(DeckNotFoundError):
            await DeckArchiver().archive(uow=uow, deck=source_deck)

        uow.deck_repo.add.assert_not_called()

    async def test_propagates_transfer_failure_without_committing(self, uow, source_deck):
        uow.deck_repo.reassign_user_decks.side_effect = RuntimeError("transfer failed")

        with pytest.raises(RuntimeError, match="transfer failed"):
            await DeckArchiver().archive(uow=uow, deck=source_deck)

        uow.commit.assert_not_awaited()

    async def test_archives_unsaved_history_without_inflating_saves(self, uow, source_deck):
        uow.deck_repo.has_archivable_user_decks.return_value = False
        uow.training_session_repo.has_by_deck_id.return_value = True
        uow.training_session_repo.reassign_deck.return_value = [8, 9]
        uow.deck_repo.reassign_user_decks.return_value = [(8, False)]

        affected = await DeckArchiver().archive(uow=uow, deck=source_deck)

        assert affected == [8, 9]
        assert uow.deck_repo.add.call_args.kwargs["deck"].saves_count == 0
        uow.training_session_repo.reassign_deck.assert_awaited_once_with(
            from_deck_id=10, to_deck_id=100, exclude_user_id=7,
        )

    async def test_preserves_owner_history_when_deleting_private_deck(self, uow, source_deck):
        source_deck.is_public = False
        uow.training_session_repo.reassign_deck.return_value = [7]
        uow.deck_repo.reassign_user_decks.return_value = [(7, False)]

        affected = await DeckArchiver().archive(uow=uow, deck=source_deck, include_owner=True)

        assert affected == [7]
        assert uow.deck_repo.add.call_args.kwargs["deck"].is_public is False
        uow.training_session_repo.reassign_deck.assert_awaited_once_with(
            from_deck_id=10, to_deck_id=100, exclude_user_id=None,
        )
        uow.deck_repo.reassign_user_decks.assert_awaited_once_with(
            from_deck_id=10, to_deck_id=100, exclude_user_id=None,
        )


class TestArchiveMany:
    async def test_returns_unique_users_for_multiple_decks(self, uow, source_deck):
        second = Deck(id=11, user_id=7, is_public=True, saves_count=1, card_links=[])
        uow.deck_repo.get_decks_with_all_cards.side_effect = [[source_deck], [second]]
        uow.deck_repo.reassign_user_decks.side_effect = [[(8, True), (9, True)], [(9, True)]]
        uow.card_repo.add_all.side_effect = None

        affected = await DeckArchiver().archive_many(uow=uow, decks=[second, source_deck])

        assert affected == [8, 9]
        assert uow.deck_repo.add.call_count == 2
        uow.commit.assert_not_awaited()

    async def test_empty_input_does_not_write(self, uow):
        affected = await DeckArchiver().archive_many(uow=uow, decks=[])

        assert affected == []
        uow.deck_repo.add.assert_not_called()


class TestDeleteUserArchiving:
    async def test_archives_saved_decks_before_deleting_owner(self, uow, source_deck):
        user = SimpleNamespace(id=7, uuid=UUID("00000000-0000-0000-0000-000000000007"))
        uow.user_repo.get_by_id = AsyncMock(return_value=user)
        uow.user_repo.delete = AsyncMock()
        uow.deck_repo.get_all_by_user_id = AsyncMock(return_value=[source_deck])
        uow.user_deck_repo.get_user_ids_by_deck_ids = AsyncMock(return_value=[8, 9])
        cache = AsyncMock()
        service = UserService(uow_factory=lambda: uow, cache_service=cache)

        await service.delete_user(current_user_id=7)

        uow.deck_repo.reassign_user_decks.assert_awaited_once_with(
            from_deck_id=10, to_deck_id=100, exclude_user_id=7,
        )
        uow.user_repo.delete.assert_awaited_once_with(user)
        uow.commit.assert_awaited_once()
        cache.invalidate_user_decks.assert_awaited_once_with(identities=[(8, 10), (9, 10)])
