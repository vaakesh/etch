from unittest.mock import create_autospec
from uuid import UUID

import pytest

from app.decks.archiver import ArchiveChanges, DeckArchiveBatchResult, DeckArchiveWorkflow
from app.decks.models import Deck
from app.decks.repository import DeckRepository, UserDeckRepository
from app.users.errors import PermissionDeniedError, UserNotFoundError
from app.users.models import User


USER_UUID = UUID("0198ad01-b200-7000-8000-000000000109")


@pytest.fixture
def delete_context(monkeypatch, users_domain_service, users_uow, users_cache):
    users_uow.deck_repo = create_autospec(DeckRepository, instance=True)
    users_uow.user_deck_repo = create_autospec(UserDeckRepository, instance=True)
    users_uow.user_repo.get_by_id.return_value = User(id=9, uuid=USER_UUID)
    users_uow.deck_repo.get_all_by_user_id.return_value = [
        Deck(id=1, user_id=9, state="active", is_public=True),
        Deck(id=2, user_id=9, state="active", is_public=False),
    ]
    users_uow.user_deck_repo.get_user_deck_keys_by_deck_ids.return_value = [(7, 1), (9, 2)]
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
    return users_domain_service, users_uow, archiver, users_cache


class TestDeleteUser:
    async def test_archives_decks_and_invalidates_all_affected_caches_after_commit(
        self, delete_context,
    ):
        service, uow, archiver, cache = delete_context
        user = uow.user_repo.get_by_id.return_value
        uow.user_repo.delete.side_effect = lambda obj: archiver.archive_owner_public_decks.assert_awaited_once_with(owner_id=9)
        uow.commit.side_effect = lambda: cache.invalidate_users.assert_not_awaited()

        await service.delete_user(current_user_id=9)

        uow.user_repo.get_by_id.assert_awaited_once_with(user_id=9, for_update=True)
        archiver.archive_owner_public_decks.assert_awaited_once_with(owner_id=9)
        uow.deck_repo.get_all_by_user_id.assert_awaited_once_with(user_id=9, public_only=False)
        uow.user_deck_repo.get_user_deck_keys_by_deck_ids.assert_awaited_once_with(deck_ids=[1, 2])
        uow.user_repo.delete.assert_awaited_once_with(user)
        uow.commit.assert_awaited_once()
        cache.invalidate_user_decks.assert_awaited_once()
        assert set(cache.invalidate_user_decks.await_args.kwargs["identities"]) == {
            (7, 1), (7, 10), (9, 2),
        }
        cache.invalidate_decks.assert_awaited_once()
        assert set(cache.invalidate_decks.await_args.kwargs["deck_ids"]) == {1, 2, 10}
        cache.invalidate_user_ids_by_uuids.assert_awaited_once_with(user_uuids=[USER_UUID])
        cache.invalidate_users.assert_awaited_once_with(user_ids=[9])
        cache.invalidate_users_settings.assert_awaited_once_with(user_ids=[9])
        cache.invalidate_library_deck_pages.assert_awaited_once_with(user_ids=[7, 8, 9])
        cache.invalidate_library_card_pages.assert_awaited_once_with(user_ids=[7, 8, 9])
        cache.invalidate_deck_cards.assert_awaited_once_with(deck_ids=[1, 2])
        cache.invalidate_cards.assert_awaited_once_with(card_ids=[100])

    async def test_deletes_user_without_owned_decks(self, delete_context):
        service, uow, archiver, cache = delete_context
        uow.deck_repo.get_all_by_user_id.return_value = []
        uow.user_deck_repo.get_user_deck_keys_by_deck_ids.return_value = []
        archiver.archive_owner_public_decks.return_value = DeckArchiveBatchResult(
            archives=[], recipient_ids=(), changes=ArchiveChanges(),
        )

        await service.delete_user(current_user_id=9)

        uow.user_repo.delete.assert_awaited_once_with(uow.user_repo.get_by_id.return_value)
        uow.commit.assert_awaited_once()
        cache.invalidate_user_decks.assert_awaited_once_with(identities=[])
        cache.invalidate_decks.assert_awaited_once_with(deck_ids=[])
        cache.invalidate_deck_cards.assert_awaited_once_with(deck_ids=[])
        cache.invalidate_cards.assert_awaited_once_with(card_ids=[])
        cache.invalidate_library_deck_pages.assert_awaited_once_with(user_ids=[9])
        cache.invalidate_library_card_pages.assert_awaited_once_with(user_ids=[9])

    @pytest.mark.parametrize(
        ("user", "expected_error"),
        [(None, UserNotFoundError), (User(id=8, uuid=USER_UUID), PermissionDeniedError)],
        ids=["missing_user", "different_owner"],
    )
    async def test_rejects_missing_or_different_user_before_archiving(
        self, delete_context, user, expected_error,
    ):
        service, uow, archiver, cache = delete_context
        uow.user_repo.get_by_id.return_value = user

        with pytest.raises(expected_error):
            await service.delete_user(current_user_id=9)

        uow.deck_repo.get_all_by_user_id.assert_not_awaited()
        archiver.archive_owner_public_decks.assert_not_awaited()
        uow.user_repo.delete.assert_not_awaited()
        uow.commit.assert_not_awaited()
        assert cache.mock_calls == []

    async def test_does_not_delete_user_when_batch_archiving_fails(self, delete_context):
        service, uow, archiver, cache = delete_context
        archiver.archive_owner_public_decks.side_effect = RuntimeError("copy failed")

        with pytest.raises(RuntimeError, match="copy failed"):
            await service.delete_user(current_user_id=9)

        uow.user_repo.delete.assert_not_awaited()
        uow.commit.assert_not_awaited()
        assert cache.mock_calls == []

    @pytest.mark.parametrize("stage", ["delete", "commit"])
    async def test_does_not_invalidate_when_database_mutation_fails(self, delete_context, stage):
        service, uow, archiver, cache = delete_context
        failing_call = uow.user_repo.delete if stage == "delete" else uow.commit
        failing_call.side_effect = RuntimeError("database failed")

        with pytest.raises(RuntimeError, match="database failed"):
            await service.delete_user(current_user_id=9)

        assert cache.mock_calls == []
        if stage == "delete":
            uow.commit.assert_not_awaited()
