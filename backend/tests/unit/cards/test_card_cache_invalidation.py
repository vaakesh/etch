from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from sqlalchemy.exc import IntegrityError

from app.cards.errors import CardAlreadyExistsError, CardNotFoundError, PermissionDeniedError
from app.cards.repository import CardRepository
from app.cards.schemas import CreateCardRequest, UpdateCardRequest
from app.cards.service import CardService
from app.decks.repository import DeckCardRepository, UserDeckRepository
from app.redis.invalidation import BumpGeneration, CacheInvalidator, DelKey
from app.redis.service import RedisCacheService
from app.service import UnitOfWork
from tests.unit.factories import make_card


NOW = datetime(2026, 9, 1, tzinfo=UTC)


def invalidated_ops(invalidator):
    invalidator.invalidate.assert_awaited_once()
    return {op for group in invalidator.invalidate.await_args.args for op in group}


@pytest.fixture
def card_cache_context():
    card = make_card()
    uow = create_autospec(UnitOfWork, instance=True)
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = False
    uow.card_repo = create_autospec(CardRepository, instance=True)
    uow.deck_card_repo = create_autospec(DeckCardRepository, instance=True)
    uow.user_deck_repo = create_autospec(UserDeckRepository, instance=True)
    uow.card_repo.get_by_uuid.return_value = card
    uow.deck_card_repo.get_all_deck_ids_by_card_ids.return_value = [200, 201]
    uow.user_deck_repo.get_library_user_ids_by_deck_ids.return_value = [7, 8, 42]
    invalidator = create_autospec(CacheInvalidator, instance=True)
    cache = create_autospec(RedisCacheService, instance=True)

    async def commit():
        invalidator.invalidate.assert_not_awaited()
        if uow.card_repo.add.called:
            created = uow.card_repo.add.call_args.args[0]
            created.id = card.id
            created.uuid = card.uuid
            created.created_at = created.updated_at = NOW

    uow.commit.side_effect = commit
    return SimpleNamespace(
        service=CardService(lambda: uow, cache, invalidator),
        uow=uow, card=card, invalidator=invalidator,
    )


class TestCreateCardInvalidation:
    async def test_refreshes_only_owner_card_library_after_commit(self, card_cache_context):
        ctx = card_cache_context

        await ctx.service.create_card(CreateCardRequest(front_text="front", back_text="back"), 42)

        assert invalidated_ops(ctx.invalidator) == {
            BumpGeneration("library:42:cards:generation"),
        }

    @pytest.mark.parametrize("failure", [
        RuntimeError("commit failed"), IntegrityError("insert", {}, Exception("duplicate")),
    ])
    async def test_does_not_invalidate_failed_creation(self, card_cache_context, failure):
        ctx = card_cache_context
        ctx.uow.commit.side_effect = failure
        expected_error = CardAlreadyExistsError if isinstance(failure, IntegrityError) else RuntimeError

        with pytest.raises(expected_error):
            await ctx.service.create_card(CreateCardRequest(front_text="front", back_text="back"), 42)

        ctx.invalidator.invalidate.assert_not_awaited()


class TestUpdateCardInvalidation:
    @pytest.mark.parametrize("payload", [
        {"front_text": "new front"}, {"back_text": "new back"},
        {"front_lang": "de"}, {"back_lang": "fr"},
    ])
    async def test_refreshes_card_and_owner_search_and_order_after_commit(self, card_cache_context, payload):
        ctx = card_cache_context

        await ctx.service.update_card(ctx.card.uuid, 42, UpdateCardRequest(**payload))

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("card:100"),
            BumpGeneration("library:42:cards:generation"),
        }

    async def test_invalidates_committed_changes_even_when_response_refresh_fails(self, card_cache_context):
        ctx = card_cache_context
        ctx.uow.card_repo.refresh.side_effect = RuntimeError("refresh failed")

        with pytest.raises(RuntimeError, match="refresh failed"):
            await ctx.service.update_card(ctx.card.uuid, 42, UpdateCardRequest(front_text="new front"))

        ctx.uow.commit.assert_awaited_once()
        assert invalidated_ops(ctx.invalidator) == {
            DelKey("card:100"),
            BumpGeneration("library:42:cards:generation"),
        }

    @pytest.mark.parametrize("failure", [
        RuntimeError("commit failed"), IntegrityError("update", {}, Exception("duplicate")),
    ])
    async def test_does_not_invalidate_failed_update(self, card_cache_context, failure):
        ctx = card_cache_context
        ctx.uow.commit.side_effect = failure
        expected_error = CardAlreadyExistsError if isinstance(failure, IntegrityError) else RuntimeError

        with pytest.raises(expected_error):
            await ctx.service.update_card(ctx.card.uuid, 42, UpdateCardRequest(front_text="new front"))

        ctx.invalidator.invalidate.assert_not_awaited()

    @pytest.mark.parametrize(("card", "expected_error"), [
        (None, CardNotFoundError), (make_card(user_id=7), PermissionDeniedError),
    ])
    async def test_does_not_invalidate_missing_or_foreign_card(self, card_cache_context, card, expected_error):
        ctx = card_cache_context
        ctx.uow.card_repo.get_by_uuid.return_value = card

        with pytest.raises(expected_error):
            await ctx.service.update_card(ctx.card.uuid, 42, UpdateCardRequest(front_text="new front"))

        ctx.invalidator.invalidate.assert_not_awaited()


class TestDeleteCardInvalidation:
    async def test_refreshes_owner_card_library_and_libraries_of_linked_deck_owners_and_savers(self, card_cache_context):
        ctx = card_cache_context

        await ctx.service.delete_card(42, ctx.card.uuid)

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("card:100"),
            DelKey("card:id-by-uuid:0198ad01-b200-7000-8000-000000000100"),
            DelKey("deck:200"), DelKey("deck:200:card-ids"),
            DelKey("deck:201"), DelKey("deck:201:card-ids"),
            BumpGeneration("library:42:cards:generation"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:7:decks:generation"),
            BumpGeneration("library:8:decks:generation"),
        }

    async def test_refreshes_only_owner_card_library_when_card_has_no_decks(self, card_cache_context):
        ctx = card_cache_context
        ctx.uow.deck_card_repo.get_all_deck_ids_by_card_ids.return_value = []
        ctx.uow.user_deck_repo.get_library_user_ids_by_deck_ids.return_value = []

        await ctx.service.delete_card(42, ctx.card.uuid)

        assert invalidated_ops(ctx.invalidator) == {
            DelKey("card:100"),
            DelKey("card:id-by-uuid:0198ad01-b200-7000-8000-000000000100"),
            BumpGeneration("library:42:cards:generation"),
        }

    @pytest.mark.parametrize("stage", ["audience", "delete", "flush", "positions", "count", "commit"])
    async def test_does_not_invalidate_when_transaction_fails(self, card_cache_context, stage):
        ctx = card_cache_context
        boundaries = {
            "audience": ctx.uow.user_deck_repo.get_library_user_ids_by_deck_ids,
            "delete": ctx.uow.card_repo.delete,
            "flush": ctx.uow.flush,
            "positions": ctx.uow.deck_card_repo.normalize_positions,
            "count": ctx.uow.deck_card_repo.update_cards_count,
            "commit": ctx.uow.commit,
        }
        boundaries[stage].side_effect = RuntimeError("transaction failed")

        with pytest.raises(RuntimeError, match="transaction failed"):
            await ctx.service.delete_card(42, ctx.card.uuid)

        ctx.invalidator.invalidate.assert_not_awaited()
