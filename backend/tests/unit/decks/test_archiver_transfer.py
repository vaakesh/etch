from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.cards.models import Card
from app.decks.archiver import (
    ArchiveChanges,
    DeckCopyResult,
    DeckProgressConflictError,
    DeckTransferUserProgress,
)
from app.decks.models import Deck, UserDeck
from app.training_sessions.models import (
    TrainingSession,
    TrainingSessionItem,
    TrainingSessionStatus,
)


SOURCE_UUID = UUID("0198ad01-b200-7000-8000-000000000101")
TARGET_UUID = UUID("0198ad01-b200-7000-8000-000000000102")
KEY_ONE = UUID("0198ad01-b200-7000-8000-000000000201")
KEY_TWO = UUID("0198ad01-b200-7000-8000-000000000202")
KEY_REMOVED = UUID("0198ad01-b200-7000-8000-000000000203")
STARTED_AT = datetime(2026, 1, 2, tzinfo=UTC)
FINISHED_AT = datetime(2026, 1, 3, tzinfo=UTC)


@pytest.fixture
def transfer_context():
    uow = MagicMock()
    uow.flush = AsyncMock()
    uow.training_session_repo.has_by_deck_id = AsyncMock(return_value=False)
    uow.user_deck_repo.get_user_ids_by_deck_ids = AsyncMock(return_value=[])
    uow.training_session_repo.lock_for_transfer = AsyncMock(return_value=[])
    uow.training_session_item_repo.lock_for_transfer = AsyncMock(return_value=[])
    uow.user_deck_repo.lock_for_transfer = AsyncMock(return_value=[])
    uow.card_repo.get_by_ids = AsyncMock(return_value=[])
    uow.user_deck_repo.count_saved = AsyncMock(return_value=0)

    source = Deck(
        id=1, uuid=SOURCE_UUID, user_id=9, state="active", saves_count=1,
    )
    target = Deck(
        id=2, uuid=TARGET_UUID, user_id=None, state="archived",
        source_deck_uuid_snapshot=SOURCE_UUID, saves_count=0,
    )
    copied = DeckCopyResult(
        deck=target, card_id_map={11: 21, 12: 22},
        changes=ArchiveChanges(), source_deck=source,
    )
    return DeckTransferUserProgress(uow), uow, source, copied


class TestDeckTransferUserProgress:
    async def test_moves_history_and_restores_missing_user_state(self, transfer_context):
        transfer, uow, source, copied = transfer_context
        completed = TrainingSession(
            id=101, user_id=7, deck_id=1,
            deck_title_snapshot="Original title",
            status=TrainingSessionStatus.COMPLETED,
            correct_count=1, wrong_count=1,
            started_at=STARTED_AT, finished_at=FINISHED_AT,
        )
        in_progress = TrainingSession(
            id=102, user_id=8, deck_id=1,
            status=TrainingSessionStatus.IN_PROGRESS,
            started_at=STARTED_AT,
        )
        first_item = TrainingSessionItem(
            id=1001, training_session_id=101,
            original_card_id=11, learning_key_snapshot=KEY_ONE,
            prompt_text="first", answer_text="one",
        )
        second_item = TrainingSessionItem(
            id=1002, training_session_id=101,
            original_card_id=None, learning_key_snapshot=KEY_TWO,
            prompt_text="second", answer_text="two",
        )
        removed_item = TrainingSessionItem(
            id=1003, training_session_id=102,
            original_card_id=13, learning_key_snapshot=KEY_REMOVED,
            prompt_text="removed", answer_text="three",
        )
        saved_state = UserDeck(
            user_id=7, deck_id=1, sessions_count=1,
            correct_count=1, wrong_count=1,
            last_studied_at=FINISHED_AT, added_at=STARTED_AT,
            is_saved=True, is_favourite=True, last_seen_version=9,
        )
        uow.training_session_repo.lock_for_transfer.return_value = [
            completed, in_progress,
        ]
        uow.training_session_item_repo.lock_for_transfer.return_value = [
            first_item, second_item, removed_item,
        ]
        uow.user_deck_repo.lock_for_transfer.return_value = [saved_state]
        uow.card_repo.get_by_ids.return_value = [
            Card(id=21, learning_key=KEY_ONE),
            Card(id=22, learning_key=KEY_TWO),
        ]

        changes = await transfer.transfer(copied)

        assert (completed.deck_id, in_progress.deck_id) == (2, 2)
        assert completed.deck_title_snapshot == "Original title"
        assert (first_item.original_card_id, second_item.original_card_id) == (21, 22)
        assert removed_item.original_card_id is None
        assert (first_item.prompt_text, removed_item.answer_text) == ("first", "three")
        assert (saved_state.deck_id, saved_state.is_saved, saved_state.is_favourite) == (
            2, True, True,
        )
        restored = uow.user_deck_repo.add.call_args.args[0]
        assert (
            restored.user_id, restored.deck_id, restored.sessions_count,
            restored.correct_count, restored.wrong_count,
            restored.last_studied_at, restored.added_at,
        ) == (8, 2, 0, 0, 0, None, STARTED_AT)
        assert (source.saves_count, copied.deck.saves_count) == (0, 0)
        assert changes.user_ids == {7, 8}
        assert changes.user_deck_keys == {
            (7, 1), (7, 2), (8, 1), (8, 2),
        }

    async def test_restores_completed_session_counters_without_user_state(
        self, transfer_context,
    ):
        transfer, uow, source, copied = transfer_context
        completed = TrainingSession(
            id=101, user_id=7, deck_id=1,
            status=TrainingSessionStatus.COMPLETED,
            correct_count=2, wrong_count=1,
            started_at=STARTED_AT, finished_at=FINISHED_AT,
        )
        uow.training_session_repo.lock_for_transfer.return_value = [completed]
        uow.card_repo.get_by_ids.return_value = [
            Card(id=21, learning_key=KEY_ONE),
            Card(id=22, learning_key=KEY_TWO),
        ]

        await transfer.transfer(copied)

        restored = uow.user_deck_repo.add.call_args.args[0]
        assert (
            restored.user_id, restored.deck_id, restored.sessions_count,
            restored.correct_count, restored.wrong_count,
            restored.last_studied_at, restored.added_at,
        ) == (7, 2, 1, 2, 1, FINISHED_AT, STARTED_AT)

    async def test_private_copy_only_moves_its_owners_progress(self, transfer_context):
        transfer, uow, source, copied = transfer_context
        copied.deck.user_id = 7
        copied.deck.state = "active"
        copied.deck.version = 1
        state = UserDeck(
            user_id=7, deck_id=1, is_saved=True,
            is_favourite=True, last_seen_version=9,
        )
        uow.user_deck_repo.lock_for_transfer.return_value = [state]
        uow.card_repo.get_by_ids.return_value = [
            Card(id=21, learning_key=KEY_ONE),
            Card(id=22, learning_key=KEY_TWO),
        ]

        changes = await transfer.transfer(copied)

        uow.training_session_repo.lock_for_transfer.assert_awaited_once_with(1, (7,))
        uow.user_deck_repo.lock_for_transfer.assert_awaited_once_with(1, (7,))
        assert (state.deck_id, state.is_saved, state.is_favourite) == (2, False, True)
        assert state.last_seen_version == 1
        assert changes.user_ids == {7}

    async def test_rejects_target_with_existing_history(self, transfer_context):
        transfer, uow, source, copied = transfer_context
        uow.training_session_repo.has_by_deck_id.return_value = True

        with pytest.raises(DeckProgressConflictError):
            await transfer.transfer(copied)

        uow.training_session_repo.lock_for_transfer.assert_not_awaited()
        uow.flush.assert_not_awaited()

    async def test_rejects_other_users_for_private_copy(self, transfer_context):
        transfer, uow, source, copied = transfer_context
        copied.deck.user_id = 7
        copied.deck.state = "active"

        with pytest.raises(ValueError, match="only receive its owner's progress"):
            await transfer.transfer(copied, user_ids=[7, 8])

        uow.training_session_repo.has_by_deck_id.assert_not_awaited()
