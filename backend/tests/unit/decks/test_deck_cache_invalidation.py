from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest

from app.cards.errors import CardNotFoundError
from app.cards.repository import CardRepository
from app.cards.schemas import CreateCardRequest
from app.decks.archiver import (
    ArchiveChanges,
    DeckArchiveResult,
    DeckArchiveWorkflow,
    DeckPreservationResult,
)
from app.decks.errors import DeckCardAlreadyExistsError, DeckNotFoundError
from app.decks.models import Deck
from app.decks.repository import DeckCardRepository, DeckRepository, UserDeckRepository
from app.decks.schemas import CreateDeckRequest, UpdateDeckRequest
from app.decks.service import DeckService, UserDeckService
from app.redis.invalidation import BumpGeneration, CacheInvalidator, DelKey
from app.redis.service import RedisCacheService
from app.users.models import User
from tests.unit.factories import make_card, make_deck, make_deck_card, make_user_deck


COPY_UUID = UUID("0198ad01-b200-7000-8000-000000000201")
NOW = datetime(2026, 9, 1, tzinfo=UTC)


def invalidated_ops(invalidator):
    invalidator.invalidate.assert_awaited_once()
    return {op for group in invalidator.invalidate.await_args.args for op in group}


@pytest.fixture
def cache_context(monkeypatch):
    data = vars(make_deck()).copy()
    data.pop("owner_uuid")
    data.pop("owner_username")
    data.pop("user")
    deck = Deck(**data)
    deck.user = User(
        id=42, uuid=UUID("0198ad01-b200-7000-8000-000000000042"), username="test-user",
    )
    card = make_card()
    link = make_deck_card()
    state = make_user_deck(is_saved=True)
    invalidator = create_autospec(CacheInvalidator, instance=True)
    cache = create_autospec(RedisCacheService, instance=True)
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)

    async def commit():
        invalidator.invalidate.assert_not_awaited()

    uow.commit = AsyncMock(side_effect=commit)
    uow.deck_repo = create_autospec(DeckRepository, instance=True)
    uow.card_repo = create_autospec(CardRepository, instance=True)
    uow.deck_card_repo = create_autospec(DeckCardRepository, instance=True)
    uow.user_deck_repo = create_autospec(UserDeckRepository, instance=True)
    uow.deck_repo.get_owned_by_uuid.return_value = deck
    uow.deck_repo.get_by_uuid.return_value = deck
    uow.card_repo.get_by_uuid.return_value = card
    uow.deck_card_repo.get_by_deck_id_and_card_id.return_value = link
    uow.deck_card_repo.get_max_position.return_value = 10
    uow.user_deck_repo.get_by_user_id_and_deck_id.return_value = state
    uow.user_deck_repo.get_user_deck_keys_by_deck_ids.return_value = [(42, 200), (7, 200), (8, 200)]
    uow.user_deck_repo.get_library_user_ids_by_deck_ids.return_value = [7, 42]

    def add_link(entity):
        entity.id = 300
        entity.uuid = link.uuid
        entity.created_at = entity.updated_at = NOW

    async def flush():
        if uow.deck_repo.add.called:
            created = uow.deck_repo.add.call_args.args[0]
            created.id = 201
            created.uuid = COPY_UUID
            created.words_count = created.saves_count = 0
            created.version = 1
            created.created_at = created.updated_at = NOW
        if uow.card_repo.add_all.called:
            for entity in uow.card_repo.add_all.call_args.args[0]:
                entity.id = 101
                entity.uuid = UUID("0198ad01-b200-7000-8000-000000000101")
                entity.created_at = entity.updated_at = NOW

    uow.deck_card_repo.add.side_effect = add_link
    uow.flush = AsyncMock(side_effect=flush)
    workflow = create_autospec(DeckArchiveWorkflow, instance=True)
    workflow.delete_deck.return_value = DeckArchiveResult(None, (), ArchiveChanges())

    async def make_private(_uuid):
        deck.is_public = False
        return DeckArchiveResult(None, (), ArchiveChanges())

    workflow.make_private.side_effect = make_private
    workflow.preserve.return_value = DeckPreservationResult(
        201, COPY_UUID, False, False,
        ArchiveChanges(
            deck_ids={200, 201}, card_ids={100, 101},
            user_ids={42}, user_deck_keys={(42, 200), (42, 201)},
        ),
    )
    monkeypatch.setattr("app.decks.service.DeckArchiveWorkflow", lambda _uow: workflow)
    monkeypatch.setattr("app.decks.models.utcnow", lambda: NOW)
    return SimpleNamespace(
        service=DeckService(lambda: uow, cache, invalidator),
        state_service=UserDeckService(lambda: uow, cache, invalidator),
        uow=uow, invalidator=invalidator, deck=deck, card=card, state=state,
        workflow=workflow,
    )


class TestCreateDeckInvalidation:
    async def test_refreshes_owner_library_after_creating_deck(self, cache_context):
        ctx = cache_context

        await ctx.service.create_deck(
            CreateDeckRequest(title="New deck"), 42, ctx.deck.user.uuid, "test-user",
        )

        assert invalidated_ops(ctx.invalidator) == {
            BumpGeneration("library:42:decks:generation"),
        }


class TestUpdateDeckInvalidation:
    @pytest.mark.parametrize("payload", [
        {"title": "New title"}, {"description": "New description"},
        {"description": None},
    ])
    async def test_refreshes_search_and_favourite_order_for_owner_and_savers(self, cache_context, payload):
        ctx = cache_context

        await ctx.service.update_deck(42, ctx.deck.uuid, UpdateDeckRequest(**payload))

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:7:decks:generation"),
        }

    async def test_refreshes_library_when_private_deck_becomes_public(self, cache_context):
        ctx = cache_context
        ctx.deck.is_public = False

        await ctx.service.update_deck(42, ctx.deck.uuid, UpdateDeckRequest(is_public=True))

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:7:decks:generation"),
        }

    async def test_clears_transferred_states_when_deck_becomes_private(self, cache_context):
        ctx = cache_context
        ctx.workflow.make_private.side_effect = None
        ctx.workflow.make_private.return_value = DeckArchiveResult(
            None, (7,), ArchiveChanges(
                deck_ids={200, 201}, user_ids={8},
                user_deck_keys={(7, 200), (7, 201), (9, 200), (9, 201)},
            ),
        )

        await ctx.service.update_deck(42, ctx.deck.uuid, UpdateDeckRequest(is_public=False))

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"), DelKey("deck:201"),
            DelKey("deck:user-deck:7:200"), DelKey("deck:user-deck:7:201"),
            DelKey("deck:user-deck:9:200"), DelKey("deck:user-deck:9:201"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:7:decks:generation"),
        }

    async def test_does_not_invalidate_unchanged_private_deck(self, cache_context):
        ctx = cache_context
        ctx.deck.is_public = False

        await ctx.service.update_deck(42, ctx.deck.uuid, UpdateDeckRequest(is_public=False))

        ctx.invalidator.invalidate.assert_not_awaited()
        ctx.workflow.make_private.assert_not_awaited()


class TestDeleteDeckInvalidation:
    async def test_clears_deleted_and_transferred_states_including_nonrecipients(self, cache_context):
        ctx = cache_context
        ctx.workflow.delete_deck.return_value = DeckArchiveResult(
            None, (8,), ArchiveChanges(
                deck_ids={200, 201}, user_ids={9},
                user_deck_keys={(8, 200), (8, 201)},
            ),
        )

        await ctx.service.delete_deck(ctx.deck.uuid, 42)

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"), DelKey("deck:200:card-ids"), DelKey("deck:201"),
            DelKey("deck:id-by-uuid:0198ad01-b200-7000-8000-000000000200"),
            DelKey("deck:user-deck:42:200"), DelKey("deck:user-deck:7:200"),
            DelKey("deck:user-deck:8:200"), DelKey("deck:user-deck:8:201"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:7:decks:generation"),
        }

    async def test_clears_owner_library_without_archive_or_states(self, cache_context):
        ctx = cache_context
        ctx.uow.user_deck_repo.get_user_deck_keys_by_deck_ids.return_value = []
        ctx.uow.user_deck_repo.get_library_user_ids_by_deck_ids.return_value = []

        await ctx.service.delete_deck(ctx.deck.uuid, 42)

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"), DelKey("deck:200:card-ids"),
            DelKey("deck:id-by-uuid:0198ad01-b200-7000-8000-000000000200"),
            BumpGeneration("library:42:decks:generation"),
        }


class TestPreserveArchivedDeckInvalidation:
    async def test_refreshes_owner_libraries_and_transferred_progress(self, cache_context):
        ctx = cache_context

        await ctx.service.preserve_archived_deck(ctx.deck.uuid, 42)

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"), DelKey("deck:201"),
            DelKey("deck:user-deck:42:200"), DelKey("deck:user-deck:42:201"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:42:cards:generation"),
        }

    @pytest.mark.parametrize("copy_deleted", [False, True])
    async def test_does_not_invalidate_already_preserved_copy(self, cache_context, copy_deleted):
        ctx = cache_context
        ctx.workflow.preserve.return_value = DeckPreservationResult(
            None if copy_deleted else 201, COPY_UUID, True, copy_deleted, ArchiveChanges(),
        )

        await ctx.service.preserve_archived_deck(ctx.deck.uuid, 42)

        ctx.invalidator.invalidate.assert_not_awaited()


class TestAddCardToDeckInvalidation:
    async def test_refreshes_previews_counts_and_favourite_order(self, cache_context):
        ctx = cache_context
        ctx.uow.deck_card_repo.get_by_deck_id_and_card_id.return_value = None

        await ctx.service.add_card_to_deck(42, ctx.deck.uuid, ctx.card.uuid)

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"), DelKey("deck:200:card-ids"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:7:decks:generation"),
        }

    async def test_does_not_invalidate_when_link_already_exists(self, cache_context):
        ctx = cache_context

        with pytest.raises(DeckCardAlreadyExistsError):
            await ctx.service.add_card_to_deck(42, ctx.deck.uuid, ctx.card.uuid)

        ctx.invalidator.invalidate.assert_not_awaited()


class TestRemoveCardFromDeckInvalidation:
    async def test_refreshes_previews_counts_and_favourite_order(self, cache_context):
        ctx = cache_context

        await ctx.service.remove_card_from_deck(42, ctx.deck.uuid, ctx.card.uuid)

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"), DelKey("deck:200:card-ids"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:7:decks:generation"),
        }


class TestLoadCardsToDeckInvalidation:
    async def test_refreshes_owner_card_library_and_all_affected_deck_pages(self, cache_context):
        ctx = cache_context

        await ctx.service.load_cards_to_deck(
            ctx.deck.uuid,
            [CreateCardRequest(front_text="front", back_text="back", front_lang="en", back_lang="ru")],
            42,
        )

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:200"), DelKey("deck:200:card-ids"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:7:decks:generation"),
            BumpGeneration("library:42:cards:generation"),
        }


class TestReorderCardsInvalidation:
    async def test_does_not_invalidate_unchanged_order(self, cache_context):
        ctx = cache_context

        await ctx.service.reorder_cards(42, ctx.deck.uuid, ctx.card.uuid, to_position=1)

        ctx.invalidator.invalidate.assert_not_awaited()


class TestSaveDeckInvalidation:
    async def test_refreshes_state_and_saving_user_library_without_deck(self, cache_context):
        ctx = cache_context
        ctx.deck.user_id = 7
        ctx.state.is_saved = False

        await ctx.state_service.save_deck(42, ctx.deck.uuid)

        assert ctx.deck.saves_count == 6
        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:user-deck:42:200"),
            BumpGeneration("library:42:decks:generation"),
        }

    async def test_does_not_invalidate_already_saved_deck(self, cache_context):
        ctx = cache_context
        ctx.deck.user_id = 7

        await ctx.state_service.save_deck(42, ctx.deck.uuid)

        ctx.invalidator.invalidate.assert_not_awaited()


class TestUnsaveDeckInvalidation:
    async def test_refreshes_state_and_saving_user_library_without_deck(self, cache_context):
        ctx = cache_context
        ctx.deck.user_id = 7
        ctx.state.is_favourite = True

        await ctx.state_service.unsave_deck(42, ctx.deck.uuid)

        assert ctx.deck.saves_count == 4
        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:user-deck:42:200"),
            BumpGeneration("library:42:decks:generation"),
        }
        assert ctx.state.is_favourite is False

    async def test_does_not_invalidate_already_unsaved_deck(self, cache_context):
        ctx = cache_context
        ctx.deck.user_id = 7
        ctx.state.is_saved = False

        await ctx.state_service.unsave_deck(42, ctx.deck.uuid)

        ctx.invalidator.invalidate.assert_not_awaited()


class TestSetFavouriteDeckInvalidation:
    @pytest.mark.parametrize("value", [True, False])
    async def test_refreshes_state_and_favourite_pages(self, cache_context, value):
        ctx = cache_context
        ctx.state.is_favourite = not value

        await ctx.state_service.set_favourite_deck(42, ctx.deck.uuid, value)

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:user-deck:42:200"),
            BumpGeneration("library:42:decks:generation"),
        }


class TestDeckMutationFailures:
    @pytest.mark.parametrize("method", [
        "create_deck", "update_deck", "delete_deck", "preserve_archived_deck",
        "add_card_to_deck", "remove_card_from_deck", "load_cards_to_deck",
        "reorder_cards", "save_deck", "unsave_deck", "set_favourite_deck",
    ])
    async def test_does_not_invalidate_when_commit_fails(self, cache_context, method):
        ctx = cache_context
        ctx.uow.commit.side_effect = RuntimeError("commit failed")
        if method == "add_card_to_deck":
            ctx.uow.deck_card_repo.get_by_deck_id_and_card_id.return_value = None
        if method in {"save_deck", "unsave_deck"}:
            ctx.deck.user_id = 7
            ctx.state.is_saved = method == "unsave_deck"
        calls = {
            "create_deck": (ctx.service, (CreateDeckRequest(title="New deck"), 42, ctx.deck.user.uuid, "test-user")),
            "update_deck": (ctx.service, (42, ctx.deck.uuid, UpdateDeckRequest(title="New title"))),
            "delete_deck": (ctx.service, (ctx.deck.uuid, 42)),
            "preserve_archived_deck": (ctx.service, (ctx.deck.uuid, 42)),
            "add_card_to_deck": (ctx.service, (42, ctx.deck.uuid, ctx.card.uuid)),
            "remove_card_from_deck": (ctx.service, (42, ctx.deck.uuid, ctx.card.uuid)),
            "load_cards_to_deck": (ctx.service, (ctx.deck.uuid, [], 42)),
            "reorder_cards": (ctx.service, (42, ctx.deck.uuid, ctx.card.uuid, 2)),
            "save_deck": (ctx.state_service, (42, ctx.deck.uuid)),
            "unsave_deck": (ctx.state_service, (42, ctx.deck.uuid)),
            "set_favourite_deck": (ctx.state_service, (42, ctx.deck.uuid, True)),
        }
        service, args = calls[method]

        with pytest.raises(RuntimeError, match="commit failed"):
            await getattr(service, method)(*args)

        ctx.invalidator.invalidate.assert_not_awaited()

    @pytest.mark.parametrize("method", ["update_deck", "delete_deck", "load_cards_to_deck"])
    async def test_does_not_invalidate_missing_owned_deck(self, cache_context, method):
        ctx = cache_context
        ctx.uow.deck_repo.get_owned_by_uuid.return_value = None
        args = {
            "update_deck": (42, ctx.deck.uuid, UpdateDeckRequest(title="New title")),
            "delete_deck": (ctx.deck.uuid, 42),
            "load_cards_to_deck": (ctx.deck.uuid, [], 42),
        }[method]

        with pytest.raises(DeckNotFoundError):
            await getattr(ctx.service, method)(*args)

        ctx.invalidator.invalidate.assert_not_awaited()

    @pytest.mark.parametrize("method", ["add_card_to_deck", "remove_card_from_deck", "reorder_cards"])
    async def test_does_not_invalidate_missing_card(self, cache_context, method):
        ctx = cache_context
        ctx.uow.card_repo.get_by_uuid.return_value = None
        args = (42, ctx.deck.uuid, ctx.card.uuid, 2) if method == "reorder_cards" else (42, ctx.deck.uuid, ctx.card.uuid)

        with pytest.raises(CardNotFoundError):
            await getattr(ctx.service, method)(*args)

        ctx.invalidator.invalidate.assert_not_awaited()
