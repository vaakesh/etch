from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from app.decks.repository import DeckRepository, UserDeckRepository
from app.redis.invalidation import BumpGeneration, CacheInvalidator, DelKey
from app.training_sessions.models import TrainingSessionStatus
from app.training_sessions.repository import (
    TrainingSessionItemRepository,
    TrainingSessionRepository,
)
from app.training_sessions.schemas import SubmittedAnswerRequest
from app.training_sessions.service import TrainingSessionService
from tests.unit.factories import (
    TEST_TRAINING_SESSION_UUID,
    make_deck,
    make_training_session,
    make_training_session_item,
    make_user_deck,
)

NOW = datetime(2026, 8, 15, 17, 0, tzinfo=UTC)


def invalidated_ops(invalidator):
    invalidator.invalidate.assert_awaited_once()
    return {op for group in invalidator.invalidate.await_args.args for op in group}


@pytest.fixture
def cache_context(monkeypatch):
    monkeypatch.setattr("app.training_sessions.service.utcnow", lambda: NOW)
    deck = make_deck()
    session = make_training_session(deck=deck)
    item = make_training_session_item(sequence_number=4)
    state = make_user_deck()
    invalidator = create_autospec(CacheInvalidator, instance=True)
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)

    async def commit():
        invalidator.invalidate.assert_not_awaited()

    async def flush():
        created = uow.training_session_repo.add.call_args.args[0]
        created.id = 400
        created.uuid = TEST_TRAINING_SESSION_UUID
        created.started_at = NOW

    uow.commit = AsyncMock(side_effect=commit)
    uow.flush = AsyncMock(side_effect=flush)
    uow.deck_repo = create_autospec(DeckRepository, instance=True)
    uow.user_deck_repo = create_autospec(UserDeckRepository, instance=True)
    uow.training_session_repo = create_autospec(
        TrainingSessionRepository, instance=True,
    )
    uow.training_session_item_repo = create_autospec(
        TrainingSessionItemRepository, instance=True,
    )
    uow.deck_repo.get_by_id.return_value = deck
    uow.deck_repo.get_by_uuid.return_value = deck
    uow.user_deck_repo.get_by_user_id_and_deck_id.return_value = state
    uow.training_session_repo.get_by_uuid.return_value = session
    uow.training_session_item_repo.get_item_by_sequence_number_and_session_id.return_value = item
    uow.training_session_item_repo.create_snapshot.return_value = [
        make_training_session_item(sequence_number=number)
        for number in range(1, 6)
    ]
    service = TrainingSessionService(
        uow_factory=lambda: uow, cache_invalidator=invalidator,
    )
    return SimpleNamespace(
        service=service, uow=uow, invalidator=invalidator,
        deck=deck, session=session, item=item, state=state,
    )


async def submit(ctx):
    return await ctx.service.submit_answer(
        user_id=42,
        training_session_uuid=ctx.session.uuid,
        sequence_number=4,
        user_answer=SubmittedAnswerRequest(action="answer", answer="hello"),
    )


async def start(ctx, user_id=42):
    return await ctx.service.start_training_session(
        user_id=user_id,
        deck_uuid=ctx.deck.uuid,
        words_per_session=5,
        prompt_side="front",
    )


class TestSubmitAnswerInvalidation:
    async def test_refreshes_state_and_library_order_when_session_completes(self, cache_context):
        ctx = cache_context
        ctx.session.answered_count = 9

        result = await submit(ctx)

        assert result.is_finished is True
        assert ctx.session.status == TrainingSessionStatus.COMPLETED
        assert ctx.state.last_studied_at == NOW
        assert ctx.state.sessions_count == 1
        assert invalidated_ops(ctx.invalidator) == {
            DelKey("deck:user-deck:42:200"),
            BumpGeneration("library:42:decks:generation"),
        }

    async def test_does_not_invalidate_unfinished_session(self, cache_context):
        ctx = cache_context

        result = await submit(ctx)

        assert result.is_finished is False
        ctx.uow.commit.assert_awaited_once()
        ctx.invalidator.invalidate.assert_not_awaited()

    async def test_does_not_invalidate_when_commit_fails(self, cache_context):
        ctx = cache_context
        ctx.session.answered_count = 9
        ctx.uow.commit.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            await submit(ctx)

        ctx.invalidator.invalidate.assert_not_awaited()


class TestStartTrainingSessionInvalidation:
    @pytest.mark.parametrize(
        ("user_id", "has_state"),
        [
            pytest.param(42, True, id="own_deck_with_state"),
            pytest.param(7, True, id="foreign_deck_with_state"),
            pytest.param(7, False, id="foreign_deck_without_state"),
        ],
    )
    async def test_does_not_invalidate_when_library_is_unchanged(
        self, cache_context, user_id, has_state,
    ):
        ctx = cache_context
        if not has_state:
            ctx.uow.user_deck_repo.get_by_user_id_and_deck_id.return_value = None

        result = await start(ctx, user_id=user_id)

        assert result.total_count == 5
        assert ctx.uow.user_deck_repo.add.called is (not has_state)
        ctx.uow.commit.assert_awaited_once()
        ctx.invalidator.invalidate.assert_not_awaited()

    async def test_refreshes_library_when_state_is_created_for_own_deck(self, cache_context):
        ctx = cache_context
        ctx.uow.user_deck_repo.get_by_user_id_and_deck_id.return_value = None

        await start(ctx)

        created = ctx.uow.user_deck_repo.add.call_args.args[0]
        assert (created.user_id, created.deck_id) == (42, 200)
        assert invalidated_ops(ctx.invalidator) == {
            BumpGeneration("library:42:decks:generation"),
        }

    async def test_does_not_invalidate_when_commit_fails(self, cache_context):
        ctx = cache_context
        ctx.uow.user_deck_repo.get_by_user_id_and_deck_id.return_value = None
        ctx.uow.commit.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            await start(ctx)

        ctx.invalidator.invalidate.assert_not_awaited()
