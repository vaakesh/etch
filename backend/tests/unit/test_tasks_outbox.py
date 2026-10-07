from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, create_autospec

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from app.decks.repository import DeckRepository
from app.decks.schemas import ArchiveCleanupBatch
from app.outbox.repository import OutboxRepository
from app.redis.outbox import EXPIRED_ARCHIVED_DECKS_CACHE_INVALIDATION_EVENT_TYPE
from app.service import UnitOfWork
from tests.unit.redis.cases import CARD_UUID, DECK_UUID


@pytest.fixture
def cleanup_context(monkeypatch):
    monkeypatch.setattr(
        "app.config.get_settings", lambda: SimpleNamespace(celery_broker_url="memory://"),
    )
    from app.celery import tasks

    uow = create_autospec(UnitOfWork, instance=True)
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = False
    uow.session = SimpleNamespace(execute=AsyncMock())
    uow.deck_repo = create_autospec(DeckRepository, instance=True)
    uow.outbox_repo = create_autospec(OutboxRepository, instance=True)
    uow.outbox_repo.mark_published.return_value = True
    uow.deck_repo.delete_expired_archived_decks.side_effect = [
        ArchiveCleanupBatch(
            decks=[(200, DECK_UUID)], cards=[(100, CARD_UUID)],
            user_deck_keys=[(42, 200)],
        ),
        ArchiveCleanupBatch(),
    ]

    async def assign_outbox_defaults():
        message = uow.outbox_repo.add.call_args.args[0]
        message.id = 17
        message.published = False

    uow.flush.side_effect = assign_outbox_defaults
    engine = SimpleNamespace(dispose=AsyncMock())
    redis = create_autospec(Redis, instance=True)
    redis.delete = AsyncMock(return_value=1)
    monkeypatch.setattr(tasks, "get_engine", lambda: engine)
    monkeypatch.setattr(tasks, "get_async_session_maker", Mock())
    monkeypatch.setattr(tasks, "get_uow_factory", lambda session_maker: lambda: uow)
    monkeypatch.setattr(tasks, "get_redis", lambda: redis)
    return tasks, uow, redis, engine


class TestCleanupExpiredArchives:
    async def test_records_event_before_commit_and_marks_it_after_invalidation(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context

        async def check_committed_before_invalidation(*keys):
            assert uow.commit.await_count == 1
            assert uow.outbox_repo.add.called
            return 1

        redis.delete.side_effect = check_committed_before_invalidation

        totals = await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        assert totals == {"decks": 1, "cards": 1, "batches": 1}
        message = uow.outbox_repo.add.call_args.args[0]
        assert message.event_type == EXPIRED_ARCHIVED_DECKS_CACHE_INVALIDATION_EVENT_TYPE
        assert message.payload == {
            "deck_ids": [200], "deck_uuids": [str(DECK_UUID)],
            "card_ids": [100], "card_uuids": [str(CARD_UUID)],
            "user_deck_keys": [[42, 200]],
        }
        uow.outbox_repo.mark_published.assert_awaited_once_with(17)
        assert uow.commit.await_count == 2
        redis.aclose.assert_awaited_once()
        engine.dispose.assert_awaited_once()

    async def test_recovers_saved_event_after_redis_failure(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        redis.delete.side_effect = ConnectionError("Redis unavailable")

        with pytest.raises(ConnectionError):
            await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        uow.commit.assert_awaited_once()
        uow.outbox_repo.mark_published.assert_not_awaited()
        message = uow.outbox_repo.add.call_args.args[0]
        uow.outbox_repo.get_pending.return_value = [message]
        redis.delete.side_effect = None

        totals = await tasks._publish_pending_expired_archive_invalidations(batch_size=100)

        assert totals == {"published": 1}
        uow.outbox_repo.mark_published.assert_awaited_once_with(17)
        assert uow.deck_repo.delete_expired_archived_decks.await_count == 1

    @pytest.mark.parametrize("stage", ["flush", "commit"])
    async def test_does_not_invalidate_when_outbox_transaction_fails(self, cleanup_context, stage):
        tasks, uow, redis, engine = cleanup_context
        getattr(uow, stage).side_effect = RuntimeError("database unavailable")

        with pytest.raises(RuntimeError, match="database unavailable"):
            await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        redis.delete.assert_not_awaited()
        uow.outbox_repo.mark_published.assert_not_awaited()

    async def test_does_not_create_event_for_empty_batch(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        uow.deck_repo.delete_expired_archived_decks.side_effect = None
        uow.deck_repo.delete_expired_archived_decks.return_value = ArchiveCleanupBatch()

        totals = await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        assert totals == {"decks": 0, "cards": 0, "batches": 0}
        uow.outbox_repo.add.assert_not_called()
        uow.commit.assert_not_awaited()
        redis.delete.assert_not_awaited()
