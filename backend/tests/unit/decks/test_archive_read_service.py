from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.cards.models import Card
from app.decks.archiver import ArchiveExpiredError
from app.decks.errors import (
    DeckNotArchivedError,
    DeckNotFoundError,
    PermissionDeniedError,
)
from app.decks.models import Deck, DeckArchiveRecipient
from app.decks.service import DeckService


ARCHIVE_UUID = UUID("0198ad01-b200-7000-8000-000000000201")
SOURCE_UUID = UUID("0198ad01-b200-7000-8000-000000000202")
CARD_UUID = UUID("0198ad01-b200-7000-8000-000000000203")
NOW = datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def archive_read_context(monkeypatch):
    monkeypatch.setattr("app.decks.service.utcnow", lambda: NOW)
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    deck = Deck(
        id=2,
        uuid=ARCHIVE_UUID,
        user_id=None,
        state="archived",
        title="Archived deck",
        description="Archived description",
        words_count=2,
        archived_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=30),
        archive_reason="deleted",
        source_deck_uuid_snapshot=SOURCE_UUID,
    )
    recipient = DeckArchiveRecipient(archive_deck_id=2, user_id=7)
    uow.deck_repo.get_with_archive_recipient = AsyncMock(
        return_value=(deck, recipient),
    )
    uow.deck_card_repo.get_cards_by_deck_id = AsyncMock(return_value=[])
    service = DeckService(
        uow_factory=lambda: uow,
        cache_service=MagicMock(),
        cache_invalidator=AsyncMock(),
    )
    return service, uow, deck, recipient


class TestGetArchiveDeck:
    async def test_returns_archive_details_for_recipient(self, archive_read_context):
        service, uow, deck, recipient = archive_read_context

        result = await service.get_archive_deck(ARCHIVE_UUID, user_id=7)

        assert result.model_dump() == {
            "uuid": ARCHIVE_UUID,
            "title": "Archived deck",
            "description": "Archived description",
            "words_count": 2,
            "archived_at": NOW - timedelta(days=1),
            "expires_at": NOW + timedelta(days=30),
            "archive_reason": "deleted",
            "source_deck_uuid_snapshot": SOURCE_UUID,
            "preserved_deck_uuid": None,
        }
        uow.deck_repo.get_with_archive_recipient.assert_awaited_once_with(
            deck_uuid=ARCHIVE_UUID, user_id=7,
        )

    async def test_rejects_active_deck(self, archive_read_context):
        service, uow, deck, recipient = archive_read_context
        deck.state = "active"

        with pytest.raises(DeckNotArchivedError):
            await service.get_archive_deck(ARCHIVE_UUID, user_id=7)

    async def test_rejects_missing_deck(self, archive_read_context):
        service, uow, deck, recipient = archive_read_context
        uow.deck_repo.get_with_archive_recipient.return_value = None

        with pytest.raises(DeckNotFoundError):
            await service.get_archive_deck(ARCHIVE_UUID, user_id=7)

    async def test_rejects_user_without_recipient_row(self, archive_read_context):
        service, uow, deck, recipient = archive_read_context
        uow.deck_repo.get_with_archive_recipient.return_value = (deck, None)

        with pytest.raises(PermissionDeniedError):
            await service.get_archive_deck(ARCHIVE_UUID, user_id=8)

    async def test_rejects_archive_at_expiry(self, archive_read_context):
        service, uow, deck, recipient = archive_read_context
        deck.expires_at = NOW

        with pytest.raises(ArchiveExpiredError):
            await service.get_archive_deck(ARCHIVE_UUID, user_id=7)


class TestGetArchiveCards:
    async def test_returns_ordered_page_for_recipient(self, archive_read_context):
        service, uow, deck, recipient = archive_read_context
        uow.deck_card_repo.get_cards_by_deck_id.return_value = [Card(
            id=3,
            uuid=CARD_UUID,
            user_id=None,
            front_text="front",
            back_text="back",
            front_lang="en",
            back_lang="ru",
            updated_at=NOW - timedelta(days=1),
        )]

        result = await service.get_archive_cards(
            ARCHIVE_UUID, user_id=7, offset=5, limit=10,
        )

        assert [card.model_dump() for card in result] == [{
            "uuid": CARD_UUID,
            "front_text": "front",
            "back_text": "back",
            "front_lang": "en",
            "back_lang": "ru",
            "updated_at": NOW - timedelta(days=1),
        }]
        uow.deck_card_repo.get_cards_by_deck_id.assert_awaited_once_with(
            deck_id=2, offset=5, limit=10,
        )

    async def test_does_not_read_cards_without_archive_access(
        self, archive_read_context,
    ):
        service, uow, deck, recipient = archive_read_context
        uow.deck_repo.get_with_archive_recipient.return_value = (deck, None)

        with pytest.raises(PermissionDeniedError):
            await service.get_archive_cards(ARCHIVE_UUID, user_id=8)

        uow.deck_card_repo.get_cards_by_deck_id.assert_not_awaited()
