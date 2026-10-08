from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, call
from uuid import UUID

import pytest

from app.decks.archiver import (
    ArchiveChanges,
    ArchiveExpiredError,
    ArchiveReason,
    DeckArchiveWorkflow,
    DeckCopyResult,
)
from app.decks.errors import PermissionDeniedError
from app.cards.models import Card
from app.decks.archiver import DeckContentCopier
from app.decks.models import Deck, DeckArchiveRecipient, DeckCard


SOURCE_UUID = UUID("0198ad01-b200-7000-8000-000000000101")
ARCHIVE_UUID = UUID("0198ad01-b200-7000-8000-000000000102")
PRIVATE_UUID = UUID("0198ad01-b200-7000-8000-000000000103")
SECOND_SOURCE_UUID = UUID("0198ad01-b200-7000-8000-000000000104")
SECOND_ARCHIVE_UUID = UUID("0198ad01-b200-7000-8000-000000000105")
CARD_UUID = UUID("0198ad01-b200-7000-8000-000000000106")
LEARNING_KEY = UUID("0198ad01-b200-7000-8000-000000000107")
NOW = datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def workflow_context():
    uow = MagicMock()
    uow.flush = AsyncMock()
    uow.user_deck_repo.get_archive_recipient_user_ids = AsyncMock(return_value=[])
    uow.training_session_repo.get_user_ids_by_deck_id = AsyncMock(return_value=[])
    uow.user_deck_repo.get_archive_recipient_pairs = AsyncMock(return_value=[])
    uow.deck_repo.lock_owned_public_deck_graphs = AsyncMock(return_value=[])
    uow.user_deck_repo.count_saved = AsyncMock(return_value=0)
    uow.deck_repo.get_archive_recipient_for_update = AsyncMock(return_value=None)
    source = Deck(id=1, uuid=SOURCE_UUID, user_id=9, state="active", is_public=True)
    archive = Deck(
        id=2, uuid=ARCHIVE_UUID, user_id=None, state="archived",
        expires_at=NOW + timedelta(days=30),
    )
    workflow = DeckArchiveWorkflow(uow, clock=lambda: NOW)
    workflow.copier._lock_source_graph = AsyncMock(return_value=(source, [], []))
    workflow.copier.create_copy = AsyncMock()
    workflow.copier.create_archive = AsyncMock(return_value=DeckCopyResult(
        deck=archive, card_id_map={}, changes=ArchiveChanges(), source_deck=source,
    ))
    workflow.copier.create_archives_batch = AsyncMock(return_value=[])
    workflow.progress.transfer = AsyncMock(return_value=ArchiveChanges())
    return workflow, uow, source, archive


class TestArchiveDeck:
    async def test_creates_recipients_for_saved_and_training_users(self, workflow_context):
        workflow, uow, source, archive = workflow_context
        uow.user_deck_repo.get_archive_recipient_user_ids.return_value = [7, 9]
        uow.training_session_repo.get_user_ids_by_deck_id.return_value = [8, 9]

        result = await workflow.archive_deck(
            SOURCE_UUID, reason=ArchiveReason.MADE_PRIVATE,
        )

        assert result.archive is archive
        assert result.recipient_ids == (7, 8)
        recipients = uow.deck_repo.add_archive_recipients.call_args.args[0]
        assert [(row.archive_deck_id, row.user_id) for row in recipients] == [
            (2, 7), (2, 8),
        ]
        workflow.progress.transfer.assert_awaited_once_with(
            workflow.copier.create_archive.return_value, user_ids=(7, 8),
        )

    async def test_skips_archive_when_nobody_has_progress(self, workflow_context):
        workflow, uow, source, archive = workflow_context

        result = await workflow.archive_deck(
            SOURCE_UUID, reason=ArchiveReason.DELETED,
        )

        assert result.archive is None
        assert result.recipient_ids == ()
        workflow.copier.create_archive.assert_not_awaited()
        uow.deck_repo.add_archive_recipients.assert_not_called()


class TestArchiveOwnerPublicDecks:
    async def test_copies_only_public_decks_with_other_user_deck_recipients_in_one_batch(
        self, workflow_context,
    ):
        workflow, uow, first, first_archive = workflow_context
        second = Deck(
            id=3, uuid=SECOND_SOURCE_UUID, user_id=9,
            state="active", is_public=True,
        )
        third = Deck(
            id=4, uuid=PRIVATE_UUID, user_id=9,
            state="active", is_public=True,
        )
        second_archive = Deck(
            id=5, uuid=SECOND_ARCHIVE_UUID, user_id=None, state="archived",
        )
        uow.deck_repo.lock_owned_public_deck_graphs.return_value = [
            (first, [], []), (second, [], []), (third, [], []),
        ]
        uow.user_deck_repo.get_archive_recipient_pairs.return_value = [
            (1, 7), (1, 9), (3, 8),
        ]
        first_copy = DeckCopyResult(
            deck=first_archive, card_id_map={},
            changes=ArchiveChanges(), source_deck=first,
        )
        second_copy = DeckCopyResult(
            deck=second_archive, card_id_map={},
            changes=ArchiveChanges(), source_deck=second,
        )
        workflow.copier.create_archives_batch.return_value = [
            first_copy, second_copy,
        ]

        result = await workflow.archive_owner_public_decks(owner_id=9)

        copied_graphs = workflow.copier.create_archives_batch.call_args.args[0]
        assert [graph[0].id for graph in copied_graphs] == [1, 3]
        assert result.recipient_ids == (7, 8)
        assert [item.recipient_ids for item in result.archives] == [(7,), (8,)]
        recipients = uow.deck_repo.add_archive_recipients.call_args.args[0]
        assert [(row.archive_deck_id, row.user_id) for row in recipients] == [
            (2, 7), (5, 8),
        ]
        assert workflow.progress.transfer.await_args_list == [
            call(first_copy, user_ids=(7,)),
            call(second_copy, user_ids=(8,)),
        ]
        workflow.copier.create_archive.assert_not_awaited()

    async def test_skips_all_copies_when_only_owner_has_user_decks(
        self, workflow_context,
    ):
        workflow, uow, source, archive = workflow_context
        uow.deck_repo.lock_owned_public_deck_graphs.return_value = [
            (source, [], []),
        ]
        uow.user_deck_repo.get_archive_recipient_pairs.return_value = [
            (1, 9),
        ]

        result = await workflow.archive_owner_public_decks(owner_id=9)

        assert result.archives == []
        assert result.recipient_ids == ()
        workflow.copier.create_archives_batch.assert_not_awaited()
        workflow.progress.transfer.assert_not_awaited()


class TestCreateArchivesBatch:
    async def test_inserts_all_decks_cards_and_links_in_three_batches(self):
        uow = MagicMock()
        first = Deck(
            id=1, uuid=SOURCE_UUID, user_id=9, state="active",
            is_public=True, title="First deck", version=2,
        )
        second = Deck(
            id=3, uuid=SECOND_SOURCE_UUID, user_id=9, state="active",
            is_public=True, title="Second deck", version=3,
        )
        shared_card = Card(
            id=11, uuid=CARD_UUID, learning_key=LEARNING_KEY,
            user_id=9, front_text="front", back_text="back",
            front_lang="en", back_lang="ru",
        )

        async def assign_database_ids():
            if uow.deck_repo.add_all.called:
                for index, target in enumerate(
                    uow.deck_repo.add_all.call_args.args[0], start=1,
                ):
                    target.id = 20 + index
                    target.uuid = ARCHIVE_UUID if index == 1 else SECOND_ARCHIVE_UUID
            if uow.card_repo.add_all.called:
                for index, card in enumerate(
                    uow.card_repo.add_all.call_args.args[0], start=1,
                ):
                    card.id = 30 + index
                    card.uuid = UUID(f"0198ad01-b200-7000-8000-{200 + index:012d}")

        uow.flush = AsyncMock(side_effect=assign_database_ids)

        copied = await DeckContentCopier(uow).create_archives_batch(
            [
                (first, [DeckCard(id=101, deck_id=1, card_id=11, position=2)],
                 [shared_card]),
                (second, [DeckCard(id=102, deck_id=3, card_id=11, position=1)],
                 [shared_card]),
            ],
            reason=ArchiveReason.OWNER_DELETED,
            retention=timedelta(days=30),
            now=NOW,
        )

        assert uow.flush.await_count == 3
        assert len(uow.deck_repo.add_all.call_args.args[0]) == 2
        assert len(uow.card_repo.add_all.call_args.args[0]) == 2
        links = uow.deck_card_repo.add_all.call_args.args[0]
        assert [(link.deck_id, link.card_id, link.position) for link in links] == [
            (21, 31, 2), (22, 32, 1),
        ]
        assert [result.card_id_map for result in copied] == [{11: 31}, {11: 32}]
        assert [
            (result.deck.state, result.deck.user_id, result.deck.is_public,
             result.deck.title, result.deck.words_count, result.deck.version,
             result.deck.source_deck_uuid_snapshot, result.deck.archive_reason,
             result.deck.archived_at, result.deck.expires_at)
            for result in copied
        ] == [
            ("archived", None, False, "First deck", 1, 2, SOURCE_UUID,
             "owner_deleted", NOW, NOW + timedelta(days=30)),
            ("archived", None, False, "Second deck", 1, 3, SECOND_SOURCE_UUID,
             "owner_deleted", NOW, NOW + timedelta(days=30)),
        ]
        assert [
            (card.user_id, card.learning_key, card.front_text, card.back_text,
             card.front_lang, card.back_lang, card.created_at, card.updated_at)
            for card in uow.card_repo.add_all.call_args.args[0]
        ] == [
            (None, LEARNING_KEY, "front", "back", "en", "ru", NOW, NOW),
            (None, LEARNING_KEY, "front", "back", "en", "ru", NOW, NOW),
        ]
        assert shared_card.user_id == 9


class TestDeleteDeck:
    async def test_deletes_source_after_archiving(self, workflow_context):
        workflow, uow, source, archive = workflow_context
        uow.deck_repo.get_by_uuid = AsyncMock(return_value=source)
        uow.deck_repo.delete = AsyncMock()

        result = await workflow.delete_deck(SOURCE_UUID)

        assert result.archive is None
        uow.deck_repo.delete.assert_awaited_once_with(source)
        uow.flush.assert_awaited_once()


class TestMakePrivate:
    async def test_keeps_source_and_removes_public_access(self, workflow_context):
        workflow, uow, source, archive = workflow_context
        uow.deck_repo.get_by_uuid = AsyncMock(return_value=source)

        result = await workflow.make_private(SOURCE_UUID)

        assert result.archive is None
        assert source.is_public is False
        uow.deck_repo.delete.assert_not_called()


class TestPreserve:
    async def test_rejects_user_without_recipient_row(self, workflow_context):
        workflow, uow, source, archive = workflow_context
        workflow.copier._lock_source_graph.return_value = (archive, [], [])

        with pytest.raises(PermissionDeniedError):
            await workflow.preserve(ARCHIVE_UUID, user_id=7)

        workflow.copier.create_copy.assert_not_awaited()

    @pytest.mark.parametrize(("copy_id", "copy_deleted"), [(3, False), (None, True)])
    @pytest.mark.parametrize("expires_at", [None, NOW, NOW + timedelta(days=30)])
    async def test_returns_preserved_snapshot_without_creating_another(
        self, workflow_context, copy_id, copy_deleted, expires_at,
    ):
        workflow, uow, source, archive = workflow_context
        archive.expires_at = expires_at
        workflow.copier._lock_source_graph.return_value = (archive, [], [])
        uow.deck_repo.get_archive_recipient_for_update.return_value = (
            DeckArchiveRecipient(
                archive_deck_id=2, user_id=7, preserved_at=NOW,
                preserved_deck_id=copy_id, preserved_deck_uuid_snapshot=PRIVATE_UUID,
            )
        )

        result = await workflow.preserve(ARCHIVE_UUID, user_id=7)

        assert result.deck_uuid == PRIVATE_UUID
        assert result.deck_id == copy_id
        assert result.already_preserved is True
        assert result.copy_deleted is copy_deleted
        workflow.copier.create_copy.assert_not_awaited()
        workflow.progress.transfer.assert_not_awaited()

    async def test_rejects_new_copy_at_expiry(self, workflow_context):
        workflow, uow, source, archive = workflow_context
        archive.expires_at = NOW
        workflow.copier._lock_source_graph.return_value = (archive, [], [])
        uow.deck_repo.get_archive_recipient_for_update.return_value = (
            DeckArchiveRecipient(archive_deck_id=2, user_id=7)
        )

        with pytest.raises(ArchiveExpiredError):
            await workflow.preserve(ARCHIVE_UUID, user_id=7)

        workflow.copier.create_copy.assert_not_awaited()

    async def test_copies_archive_and_records_private_copy(self, workflow_context):
        workflow, uow, source, archive = workflow_context
        workflow.copier._lock_source_graph.return_value = (archive, [], [])
        recipient = DeckArchiveRecipient(archive_deck_id=2, user_id=7)
        uow.deck_repo.get_archive_recipient_for_update.return_value = recipient
        private = Deck(
            id=3, uuid=PRIVATE_UUID, user_id=7, state="active",
            source_deck_uuid_snapshot=ARCHIVE_UUID,
        )
        workflow.copier.create_copy = AsyncMock(return_value=DeckCopyResult(
            deck=private, card_id_map={}, changes=ArchiveChanges(),
            source_deck=archive,
        ))

        result = await workflow.preserve(ARCHIVE_UUID, user_id=7)

        assert result.deck_uuid == PRIVATE_UUID
        assert result.already_preserved is False
        assert result.copy_deleted is False
        assert (
            recipient.preserved_at,
            recipient.preserved_deck_id,
            recipient.preserved_deck_uuid_snapshot,
        ) == (NOW, 3, PRIVATE_UUID)
        workflow.progress.transfer.assert_awaited_once_with(
            workflow.copier.create_copy.return_value, user_ids=(7,),
        )
