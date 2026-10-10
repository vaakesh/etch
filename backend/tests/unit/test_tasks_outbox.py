from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, create_autospec

import pytest
from redis.asyncio import Redis
from redis.asyncio.client import Pipeline
from redis.exceptions import ConnectionError

from app.decks.repository import DeckRepository
from app.decks.schemas import ArchiveCleanupBatch
from app.outbox.repository import OutboxRepository
from app.outbox.models import OutboxMessage
from app.redis.outbox import CACHE_INVALIDATION_EVENT_TYPE
from app.service import UnitOfWork
from tests.unit.redis.cases import CARD_UUID, DECK_UUID

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


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
    pipeline = create_autospec(Pipeline, instance=True)
    pipeline.execute = AsyncMock(return_value=[])
    redis.pipeline.return_value = pipeline
    monkeypatch.setattr(tasks, "get_engine", lambda: engine)
    monkeypatch.setattr(tasks, "get_async_session_maker", Mock())
    monkeypatch.setattr(tasks, "get_uow_factory", lambda session_maker: lambda: uow)
    monkeypatch.setattr(tasks, "get_redis", lambda: redis)
    monkeypatch.setattr(tasks, "utcnow", lambda: NOW)
    return tasks, uow, redis, engine


class TestCleanupExpiredArchives:
    async def test_records_event_before_commit_and_marks_it_after_invalidation(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context

        async def check_committed_before_invalidation(*keys):
            assert uow.commit.await_count == 1
            assert uow.outbox_repo.add.called
            return 1

        redis.pipeline.return_value.execute.side_effect = check_committed_before_invalidation

        totals = await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        assert totals == {"decks": 1, "cards": 1, "batches": 1}
        message = uow.outbox_repo.add.call_args.args[0]
        assert message.event_type == CACHE_INVALIDATION_EVENT_TYPE
        assert message.payload == {
            "scopes": [
                {"name": "deck_with_cards", "args": [200]},
                {"name": "deck_ids_by_uuids", "args": [str(DECK_UUID)]},
                {"name": "user_decks", "args": [[42, 200]]},
                {"name": "cards", "args": [100]},
                {"name": "card_ids_by_uuids", "args": [str(CARD_UUID)]},
            ],
        }
        redis.pipeline.return_value.unlink.assert_called_once_with(
            "deck:200", "deck:200:card-ids", f"deck:id-by-uuid:{DECK_UUID}",
            "deck:user-deck:42:200", "card:100", f"card:id-by-uuid:{CARD_UUID}",
        )
        uow.outbox_repo.mark_published.assert_awaited_once_with(17)
        assert uow.commit.await_count == 2
        redis.aclose.assert_awaited_once()
        engine.dispose.assert_awaited_once()

    async def test_recovers_saved_event_after_redis_failure(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        redis.pipeline.return_value.execute.side_effect = ConnectionError("Redis unavailable")

        with pytest.raises(ConnectionError):
            await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        uow.commit.assert_awaited_once()
        uow.outbox_repo.mark_published.assert_not_awaited()
        message = uow.outbox_repo.add.call_args.args[0]
        uow.outbox_repo.get_pending.return_value = [message]
        redis.pipeline.return_value.execute.side_effect = None

        totals = await tasks._publish_pending_cache_invalidations(batch_size=100)

        assert totals == {"published": 1}
        uow.outbox_repo.mark_published.assert_awaited_once_with(17)
        assert uow.deck_repo.delete_expired_archived_decks.await_count == 1

    @pytest.mark.parametrize("stage", ["flush", "commit"])
    async def test_does_not_invalidate_when_outbox_transaction_fails(self, cleanup_context, stage):
        tasks, uow, redis, engine = cleanup_context
        getattr(uow, stage).side_effect = RuntimeError("database unavailable")

        with pytest.raises(RuntimeError, match="database unavailable"):
            await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        redis.pipeline.assert_not_called()
        uow.outbox_repo.mark_published.assert_not_awaited()

    async def test_does_not_create_event_for_empty_batch(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        uow.deck_repo.delete_expired_archived_decks.side_effect = None
        uow.deck_repo.delete_expired_archived_decks.return_value = ArchiveCleanupBatch()

        totals = await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        assert totals == {"decks": 0, "cards": 0, "batches": 0}
        uow.outbox_repo.add.assert_not_called()
        uow.commit.assert_not_awaited()
        redis.pipeline.assert_not_called()

    async def test_omits_empty_scopes_when_batch_has_no_cards_or_user_decks(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        uow.deck_repo.delete_expired_archived_decks.side_effect = [
            ArchiveCleanupBatch(decks=[(200, DECK_UUID)]),
            ArchiveCleanupBatch(),
        ]

        totals = await tasks._cleanup_expired_archives(batch_size=100, max_batches=2)

        assert totals == {"decks": 1, "cards": 0, "batches": 1}
        message = uow.outbox_repo.add.call_args.args[0]
        assert message.payload == {"scopes": [
            {"name": "deck_with_cards", "args": [200]},
            {"name": "deck_ids_by_uuids", "args": [str(DECK_UUID)]},
        ]}
        redis.pipeline.return_value.unlink.assert_called_once_with(
            "deck:200", "deck:200:card-ids", f"deck:id-by-uuid:{DECK_UUID}",
        )
        uow.outbox_repo.mark_published.assert_awaited_once_with(17)


class TestPublishPendingCacheInvalidations:
    def test_schedule_uses_generic_cache_delivery_task(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context

        schedule = tasks.celery_app.conf.beat_schedule["publish-pending-cache-invalidations"]

        assert schedule == {
            "task": "maintenance.publish_pending_cache_invalidations",
            "schedule": 30.0,
            "kwargs": {"batch_size": 100},
        }
        assert tasks.publish_pending_cache_invalidations.name == "maintenance.publish_pending_cache_invalidations"

    async def test_delivers_pending_scope_events(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        uow.outbox_repo.get_pending.return_value = [
            OutboxMessage(
                id=17, published=False, event_type=CACHE_INVALIDATION_EVENT_TYPE,
                payload={"scopes": [
                    {"name": "users", "args": [42]},
                    {"name": "library_card_pages", "args": [42]},
                ]},
            ),
            OutboxMessage(
                id=18, published=False, event_type=CACHE_INVALIDATION_EVENT_TYPE,
                payload={"scopes": [
                    {"name": "deck_with_cards", "args": [200]},
                    {"name": "deck_ids_by_uuids", "args": [str(DECK_UUID)]},
                ]},
            ),
        ]

        totals = await tasks._publish_pending_cache_invalidations(batch_size=100)

        assert totals == {"published": 2}
        # события моложе 10 секунд ещё доставляет создавший их запрос
        uow.outbox_repo.get_pending.assert_awaited_once_with(
            event_types=[CACHE_INVALIDATION_EVENT_TYPE],
            created_before=datetime(2026, 10, 10, 11, 59, 50, tzinfo=UTC),
            limit=100,
        )
        assert redis.pipeline.return_value.method_calls == [
            call.unlink("user:42"),
            call.incr("library:42:cards:generation"),
            call.execute(),
            call.unlink("deck:200", "deck:200:card-ids", f"deck:id-by-uuid:{DECK_UUID}"),
            call.execute(),
        ]
        assert uow.outbox_repo.mark_published.await_args_list == [call(17), call(18)]
        redis.aclose.assert_awaited_once()
        engine.dispose.assert_awaited_once()

    async def test_retries_generation_event_after_redis_failure(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        uow.outbox_repo.get_pending.return_value = [OutboxMessage(
            id=17, published=False, event_type=CACHE_INVALIDATION_EVENT_TYPE,
            payload={"scopes": [{"name": "library_deck_pages", "args": [42]}]},
        )]
        pipeline = redis.pipeline.return_value
        pipeline.execute.side_effect = ConnectionError("Redis unavailable")

        with pytest.raises(ConnectionError):
            await tasks._publish_pending_cache_invalidations(batch_size=100)
        uow.outbox_repo.mark_published.assert_not_awaited()
        pipeline.execute.side_effect = None
        totals = await tasks._publish_pending_cache_invalidations(batch_size=100)

        assert totals == {"published": 1}
        assert pipeline.incr.call_args_list == [
            call("library:42:decks:generation"), call("library:42:decks:generation"),
        ]
        uow.outbox_repo.mark_published.assert_awaited_once_with(17)

    async def test_retries_delivered_event_after_publication_commit_fails(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        uow.outbox_repo.get_pending.return_value = [OutboxMessage(
            id=17, published=False, event_type=CACHE_INVALIDATION_EVENT_TYPE,
            payload={"scopes": [{"name": "library_deck_pages", "args": [42]}]},
        )]
        uow.commit.side_effect = RuntimeError("database unavailable")

        with pytest.raises(RuntimeError, match="database unavailable"):
            await tasks._publish_pending_cache_invalidations(batch_size=100)
        uow.commit.side_effect = None
        totals = await tasks._publish_pending_cache_invalidations(batch_size=100)

        assert totals == {"published": 1}
        assert redis.pipeline.return_value.incr.call_args_list == [
            call("library:42:decks:generation"), call("library:42:decks:generation"),
        ]
        assert uow.outbox_repo.mark_published.await_args_list == [call(17), call(17)]

    async def test_does_not_publish_invalid_scope(self, cleanup_context):
        tasks, uow, redis, engine = cleanup_context
        uow.outbox_repo.get_pending.return_value = [OutboxMessage(
            id=17, published=False, event_type=CACHE_INVALIDATION_EVENT_TYPE,
            payload={"scopes": [{"name": "__dict__", "args": []}]},
        )]

        with pytest.raises(ValueError, match="Unknown cache scope"):
            await tasks._publish_pending_cache_invalidations(batch_size=100)

        redis.pipeline.assert_not_called()
        uow.outbox_repo.mark_published.assert_not_awaited()
        redis.aclose.assert_awaited_once()
        engine.dispose.assert_awaited_once()
