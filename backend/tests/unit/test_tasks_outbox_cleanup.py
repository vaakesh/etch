from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, create_autospec

import pytest
from celery.schedules import crontab
from sqlalchemy.exc import DBAPIError

from app.outbox.repository import OutboxRepository
from app.service import UnitOfWork

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
CUTOFF_1_DAY = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


class DriverError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


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
    uow.outbox_repo = create_autospec(OutboxRepository, instance=True)
    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(tasks, "get_engine", lambda: engine)
    monkeypatch.setattr(tasks, "get_async_session_maker", Mock())
    monkeypatch.setattr(tasks, "get_uow_factory", lambda session_maker: lambda: uow)
    monkeypatch.setattr(tasks, "utcnow", lambda: NOW)
    return tasks, uow, engine


class TestCleanupPublishedOutbox:
    async def test_deletes_batches_until_partial_batch(self, cleanup_context):
        tasks, uow, engine = cleanup_context
        uow.outbox_repo.delete_published.side_effect = [2, 1]

        totals = await tasks._cleanup_published_outbox(
            batch_size=2, max_batches=5, retention_days=1,
        )

        assert totals == {"messages": 3, "batches": 2}
        assert uow.outbox_repo.delete_published.await_count == 2
        uow.outbox_repo.delete_published.assert_awaited_with(
            cutoff=CUTOFF_1_DAY, limit=2,
        )
        assert uow.commit.await_count == 2
        engine.dispose.assert_awaited_once()

    async def test_stops_after_max_batches_when_backlog_remains(self, cleanup_context):
        tasks, uow, engine = cleanup_context
        uow.outbox_repo.delete_published.return_value = 2

        totals = await tasks._cleanup_published_outbox(
            batch_size=2, max_batches=3, retention_days=1,
        )

        assert totals == {"messages": 6, "batches": 3}
        assert uow.outbox_repo.delete_published.await_count == 3
        assert uow.commit.await_count == 3

    async def test_does_not_commit_when_nothing_is_old_enough(self, cleanup_context):
        tasks, uow, engine = cleanup_context
        uow.outbox_repo.delete_published.return_value = 0

        totals = await tasks._cleanup_published_outbox(
            batch_size=2, max_batches=5, retention_days=1,
        )

        assert totals == {"messages": 0, "batches": 0}
        uow.outbox_repo.delete_published.assert_awaited_once_with(
            cutoff=CUTOFF_1_DAY, limit=2,
        )
        uow.commit.assert_not_awaited()
        engine.dispose.assert_awaited_once()

    async def test_raises_retryable_error_on_lock_timeout(self, cleanup_context):
        tasks, uow, engine = cleanup_context
        uow.outbox_repo.delete_published.side_effect = DBAPIError(
            "DELETE", {}, DriverError("55P03"),
        )

        with pytest.raises(tasks.RetryableArchiveCleanupError):
            await tasks._cleanup_published_outbox(
                batch_size=2, max_batches=5, retention_days=1,
            )

        uow.commit.assert_not_awaited()
        engine.dispose.assert_awaited_once()

    async def test_propagates_non_retryable_database_error(self, cleanup_context):
        tasks, uow, engine = cleanup_context
        uow.outbox_repo.delete_published.side_effect = DBAPIError(
            "DELETE", {}, DriverError("23503"),
        )

        with pytest.raises(DBAPIError):
            await tasks._cleanup_published_outbox(
                batch_size=2, max_batches=5, retention_days=1,
            )

        engine.dispose.assert_awaited_once()


class TestCleanupPublishedOutboxTask:
    def test_schedule_runs_hourly_with_day_retention(self, cleanup_context):
        tasks, uow, engine = cleanup_context

        schedule = tasks.celery_app.conf.beat_schedule["cleanup-published-outbox-hourly"]

        assert schedule == {
            "task": "maintenance.cleanup_published_outbox",
            "schedule": crontab(minute=15),
            "kwargs": {"batch_size": 1000, "max_batches": 20, "retention_days": 1},
        }
        assert tasks.cleanup_published_outbox.name == "maintenance.cleanup_published_outbox"

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"batch_size": 0}, "batch_size must be between 1 and 5000"),
            ({"batch_size": 5001}, "batch_size must be between 1 and 5000"),
            ({"max_batches": 0}, "max_batches must be between 1 and 100"),
            ({"max_batches": 101}, "max_batches must be between 1 and 100"),
            ({"retention_days": 0}, "retention_days must be between 1 and 365"),
            ({"retention_days": 366}, "retention_days must be between 1 and 365"),
        ],
    )
    def test_rejects_arguments_outside_allowed_range(self, cleanup_context, kwargs, message):
        tasks, uow, engine = cleanup_context

        with pytest.raises(ValueError, match=message):
            tasks.cleanup_published_outbox(**kwargs)

        uow.outbox_repo.delete_published.assert_not_awaited()
