from unittest.mock import create_autospec
from uuid import UUID

import pytest

from app.decks.archiver import ArchiveChanges, DeckArchiveBatchResult, DeckArchiveWorkflow
from app.decks.models import Deck
from app.decks.repository import DeckRepository, UserDeckRepository
from app.cards.repository import CardRepository
from app.decks.repository import DeckCardRepository
from app.redis.invalidation import BumpGeneration, DelKey
from app.users.errors import PermissionDeniedError, UserNotFoundError
from app.users.models import User


from tests.unit.outbox_helpers import (
    assert_invalidation_delivered_from_outbox,
    first_commit_precedes_invalidation,
)

USER_UUID = UUID("0198ad01-b200-7000-8000-000000000109")
PUBLIC_DECK_UUID = UUID("0198ad01-b200-7000-8000-000000000201")
PRIVATE_DECK_UUID = UUID("0198ad01-b200-7000-8000-000000000202")
CARD_UUID = UUID("0198ad01-b200-7000-8000-000000000301")
ORPHAN_CARD_UUID = UUID("0198ad01-b200-7000-8000-000000000302")


@pytest.fixture
def delete_context(
    monkeypatch, users_domain_service, users_uow, users_cache, users_invalidator,
):
    users_uow.deck_repo = create_autospec(DeckRepository, instance=True)
    users_uow.user_deck_repo = create_autospec(UserDeckRepository, instance=True)
    users_uow.card_repo = create_autospec(CardRepository, instance=True)
    users_uow.deck_card_repo = create_autospec(DeckCardRepository, instance=True)
    users_uow.user_repo.get_by_id.return_value = User(id=9, uuid=USER_UUID)
    users_uow.deck_repo.get_all_by_user_id.return_value = [
        Deck(id=1, uuid=PUBLIC_DECK_UUID, user_id=9, state="active", is_public=True),
        Deck(id=2, uuid=PRIVATE_DECK_UUID, user_id=9, state="active", is_public=False),
    ]
    users_uow.user_deck_repo.get_user_deck_keys_by_deck_ids.return_value = [(7, 1), (9, 2)]
    users_uow.user_deck_repo.get_library_user_ids_by_deck_ids.return_value = [7, 9]
    users_uow.user_deck_repo.get_user_deck_keys_by_user_id.return_value = [(9, 2), (9, 90)]
    users_uow.card_repo.get_identities_by_user_id.return_value = [
        (100, CARD_UUID), (101, ORPHAN_CARD_UUID),
    ]
    users_uow.deck_card_repo.get_all_deck_ids_by_card_ids.return_value = [1, 2]
    archiver = create_autospec(DeckArchiveWorkflow, instance=True)
    archiver.archive_owner_public_decks.return_value = DeckArchiveBatchResult(
        archives=[],
        recipient_ids=(7, 8),
        changes=ArchiveChanges(
            deck_ids={1, 10}, card_ids={100},
            user_deck_keys={(7, 10)},
        ),
    )
    monkeypatch.setattr("app.users.service.DeckArchiveWorkflow", lambda unit: archiver)
    return users_domain_service, users_uow, archiver, users_cache, users_invalidator


class TestDeleteUser:
    async def test_archives_decks_and_invalidates_all_affected_caches_after_commit(
        self, delete_context,
    ):
        service, uow, archiver, cache, invalidator = delete_context
        user = uow.user_repo.get_by_id.return_value
        uow.user_repo.delete.side_effect = lambda obj: archiver.archive_owner_public_decks.assert_awaited_once_with(owner_id=9)
        uow.commit.side_effect = first_commit_precedes_invalidation(uow, invalidator)

        await service.delete_user(current_user_id=9)

        uow.user_repo.get_by_id.assert_awaited_once_with(user_id=9, for_update=True)
        archiver.archive_owner_public_decks.assert_awaited_once_with(owner_id=9)
        uow.deck_repo.get_all_by_user_id.assert_awaited_once_with(user_id=9, public_only=False)
        uow.user_deck_repo.get_user_deck_keys_by_deck_ids.assert_awaited_once_with(deck_ids=[1, 2])
        uow.user_deck_repo.get_user_deck_keys_by_user_id.assert_awaited_once_with(user_id=9)
        uow.card_repo.get_identities_by_user_id.assert_awaited_once_with(user_id=9)
        uow.deck_card_repo.get_all_deck_ids_by_card_ids.assert_awaited_once_with(card_ids=[100, 101])
        uow.user_repo.delete.assert_awaited_once_with(user)
        assert uow.commit.await_count == 2
        assert_invalidation_delivered_from_outbox(uow, invalidator)
        groups = invalidator.invalidate.await_args.args
        assert {op for group in groups for op in group} == {
            DelKey("user:9"), DelKey(f"user:id-by-uuid:{USER_UUID}"),
            DelKey("user:9:settings"),
            BumpGeneration("library:9:decks:generation"),
            BumpGeneration("library:9:cards:generation"),
            BumpGeneration("library:7:decks:generation"),
            DelKey("deck:user-deck:7:1"), DelKey("deck:user-deck:7:10"),
            DelKey("deck:user-deck:9:2"), DelKey("deck:user-deck:9:90"),
            DelKey("deck:1"), DelKey("deck:2"), DelKey("deck:10"),
            DelKey("deck:1:card-ids"), DelKey("deck:2:card-ids"),
            DelKey("deck:10:card-ids"),
            DelKey(f"deck:id-by-uuid:{PUBLIC_DECK_UUID}"),
            DelKey(f"deck:id-by-uuid:{PRIVATE_DECK_UUID}"),
            DelKey("card:100"), DelKey("card:101"),
            DelKey(f"card:id-by-uuid:{CARD_UUID}"),
            DelKey(f"card:id-by-uuid:{ORPHAN_CARD_UUID}"),
        }
        assert cache.mock_calls == []

    async def test_deletes_user_without_owned_decks(self, delete_context):
        service, uow, archiver, cache, invalidator = delete_context
        uow.deck_repo.get_all_by_user_id.return_value = []
        uow.user_deck_repo.get_user_deck_keys_by_deck_ids.return_value = []
        uow.user_deck_repo.get_library_user_ids_by_deck_ids.return_value = []
        uow.user_deck_repo.get_user_deck_keys_by_user_id.return_value = []
        uow.card_repo.get_identities_by_user_id.return_value = []
        uow.deck_card_repo.get_all_deck_ids_by_card_ids.return_value = []
        archiver.archive_owner_public_decks.return_value = DeckArchiveBatchResult(
            archives=[], recipient_ids=(), changes=ArchiveChanges(),
        )

        await service.delete_user(current_user_id=9)

        uow.user_repo.delete.assert_awaited_once_with(uow.user_repo.get_by_id.return_value)
        assert uow.commit.await_count == 2
        assert_invalidation_delivered_from_outbox(uow, invalidator)
        groups = invalidator.invalidate.await_args.args
        assert {op for group in groups for op in group} == {
            DelKey("user:9"), DelKey(f"user:id-by-uuid:{USER_UUID}"),
            DelKey("user:9:settings"),
            BumpGeneration("library:9:decks:generation"),
            BumpGeneration("library:9:cards:generation"),
        }
        assert cache.mock_calls == []

    async def test_invalidates_decks_referencing_deleted_cards_and_archive_consumers(
        self, delete_context,
    ):
        service, uow, archiver, cache, invalidator = delete_context
        uow.deck_card_repo.get_all_deck_ids_by_card_ids.return_value = [1, 2, 3]
        uow.user_deck_repo.get_user_deck_keys_by_deck_ids.return_value = [
            (7, 1), (9, 2), (11, 3),
        ]
        uow.user_deck_repo.get_library_user_ids_by_deck_ids.return_value = [7, 9, 10, 11]
        archiver.archive_owner_public_decks.return_value.changes.user_ids = {12}
        archiver.archive_owner_public_decks.return_value.changes.user_deck_keys.add((13, 10))

        await service.delete_user(current_user_id=9)

        uow.user_deck_repo.get_user_deck_keys_by_deck_ids.assert_awaited_once_with(
            deck_ids=[1, 2, 3],
        )
        invalidator.invalidate.assert_awaited_once()
        groups = invalidator.invalidate.await_args.args
        ops = [op for group in groups for op in group]
        assert DelKey("deck:3") in ops
        assert DelKey("deck:3:card-ids") in ops
        assert DelKey("deck:user-deck:11:3") in ops
        assert DelKey("deck:user-deck:13:10") in ops
        assert {op for op in ops if isinstance(op, BumpGeneration)} == {
            BumpGeneration("library:9:decks:generation"),
            BumpGeneration("library:9:cards:generation"),
            BumpGeneration("library:7:decks:generation"),
            BumpGeneration("library:10:decks:generation"),
            BumpGeneration("library:11:decks:generation"),
        }
        assert cache.mock_calls == []

    async def test_invalidates_orphan_cards_and_foreign_deck_state_without_owned_decks(
        self, delete_context,
    ):
        service, uow, archiver, cache, invalidator = delete_context
        uow.deck_repo.get_all_by_user_id.return_value = []
        uow.card_repo.get_identities_by_user_id.return_value = [(101, ORPHAN_CARD_UUID)]
        uow.deck_card_repo.get_all_deck_ids_by_card_ids.return_value = []
        uow.user_deck_repo.get_user_deck_keys_by_deck_ids.return_value = []
        uow.user_deck_repo.get_library_user_ids_by_deck_ids.return_value = []
        uow.user_deck_repo.get_user_deck_keys_by_user_id.return_value = [(9, 90)]
        archiver.archive_owner_public_decks.return_value = DeckArchiveBatchResult(
            archives=[], recipient_ids=(), changes=ArchiveChanges(),
        )

        await service.delete_user(current_user_id=9)

        invalidator.invalidate.assert_awaited_once()
        groups = invalidator.invalidate.await_args.args
        assert {op for group in groups for op in group} == {
            DelKey("user:9"), DelKey(f"user:id-by-uuid:{USER_UUID}"),
            DelKey("user:9:settings"),
            BumpGeneration("library:9:decks:generation"),
            BumpGeneration("library:9:cards:generation"),
            DelKey("card:101"), DelKey(f"card:id-by-uuid:{ORPHAN_CARD_UUID}"),
            DelKey("deck:user-deck:9:90"),
        }
        assert cache.mock_calls == []

    @pytest.mark.parametrize(
        ("user", "expected_error"),
        [(None, UserNotFoundError), (User(id=8, uuid=USER_UUID), PermissionDeniedError)],
        ids=["missing_user", "different_owner"],
    )
    async def test_rejects_missing_or_different_user_before_archiving(
        self, delete_context, user, expected_error,
    ):
        service, uow, archiver, cache, invalidator = delete_context
        uow.user_repo.get_by_id.return_value = user

        with pytest.raises(expected_error):
            await service.delete_user(current_user_id=9)

        uow.deck_repo.get_all_by_user_id.assert_not_awaited()
        archiver.archive_owner_public_decks.assert_not_awaited()
        uow.user_repo.delete.assert_not_awaited()
        uow.commit.assert_not_awaited()
        assert cache.mock_calls == []
        invalidator.invalidate.assert_not_awaited()

    async def test_does_not_delete_user_when_batch_archiving_fails(self, delete_context):
        service, uow, archiver, cache, invalidator = delete_context
        archiver.archive_owner_public_decks.side_effect = RuntimeError("copy failed")

        with pytest.raises(RuntimeError, match="copy failed"):
            await service.delete_user(current_user_id=9)

        uow.user_repo.delete.assert_not_awaited()
        uow.commit.assert_not_awaited()
        assert cache.mock_calls == []
        invalidator.invalidate.assert_not_awaited()

    @pytest.mark.parametrize("stage", ["delete", "commit"])
    async def test_does_not_invalidate_when_database_mutation_fails(self, delete_context, stage):
        service, uow, archiver, cache, invalidator = delete_context
        failing_call = uow.user_repo.delete if stage == "delete" else uow.commit
        failing_call.side_effect = RuntimeError("database failed")

        with pytest.raises(RuntimeError, match="database failed"):
            await service.delete_user(current_user_id=9)

        assert cache.mock_calls == []
        invalidator.invalidate.assert_not_awaited()
        uow.outbox_repo.mark_published.assert_not_awaited()
        if stage == "delete":
            uow.commit.assert_not_awaited()
