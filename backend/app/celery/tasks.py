import asyncio
from datetime import timedelta

from celery.utils.log import get_task_logger
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.celery.celery_app import celery_app
from app.common.utils import utcnow
from app.database import get_async_session_maker, get_engine
from app.deps import get_uow_factory
from app.outbox.models import OutboxMessage
from app.outbox.service import OutboxPublisher
from app.redis.deps import get_redis
from app.redis.invalidation import CacheInvalidator, dump_scopes, scopes
from app.redis.outbox import (
    CACHE_INVALIDATION_EVENT_TYPE,
    CacheInvalidationHandler,
)

logger = get_task_logger(__name__)


class RetryableArchiveCleanupError(Exception):
    """Временная ошибка БД; очистку можно повторить."""


def _is_retryable_database_error(error: DBAPIError) -> bool:
    sqlstate = (
        getattr(error.orig, "sqlstate", None)
        or getattr(error.orig, "pgcode", None)
        or ""
    )
    return (
        error.connection_invalidated  # connection invalidated
        or sqlstate.startswith("08")  # connection error
        or sqlstate in {
            "40001",  # serialization failure
            "40P01",  # deadlock detected
            "55P03",  # lock unavailable (including lock timeout)
            "57014",  # query canceled (including statement timeout)
        }
    )


async def _cleanup_expired_archives(
    batch_size: int,
    max_batches: int,
) -> dict[str, int]:
    engine = get_engine()
    uow_factory = get_uow_factory(
        get_async_session_maker()
    )
    redis = get_redis()
    invalidator = CacheInvalidator(redis=redis)
    publisher = OutboxPublisher(
        uow_factory,
        {
            CACHE_INVALIDATION_EVENT_TYPE: CacheInvalidationHandler(invalidator),
        },
    )
    totals = {"decks": 0, "cards": 0, "batches": 0}
    cutoff = utcnow()

    try:
        for _ in range(max_batches):
            async with uow_factory() as uow:
                # не держим воркер долго (тяжелый запрос/занятая строка)
                await uow.session.execute(
                    text("SET LOCAL lock_timeout = '5s'")
                )
                await uow.session.execute(
                    text("SET LOCAL statement_timeout = '60s'")
                )

                batch = await uow.deck_repo.delete_expired_archived_decks(
                    now=cutoff,
                    limit=batch_size,
                )

                if not batch.decks:
                    break

                payload = dump_scopes(
                    scopes.deck_with_cards(*(deck_id for deck_id, _ in batch.decks)),
                    scopes.deck_ids_by_uuids(*(deck_uuid for _, deck_uuid in batch.decks)),
                    scopes.user_decks(*batch.user_deck_keys),
                    scopes.cards(*(card_id for card_id, _ in batch.cards)),
                    scopes.card_ids_by_uuids(*(card_uuid for _, card_uuid in batch.cards)),
                )
                message = OutboxMessage(
                    event_type=CACHE_INVALIDATION_EVENT_TYPE,
                    payload=payload,
                )
                uow.outbox_repo.add(message)
                await uow.flush()
                await uow.commit()

            await publisher.publish(message)

            totals["decks"] += len(batch.decks)
            totals["cards"] += len(batch.cards)
            totals["batches"] += 1

            logger.info(
                "archive cleanup batch: decks=%s cards=%s",
                len(batch.decks),
                len(batch.cards),
            )
        logger.info("archive cleanup finished: %s", totals)
        return totals
    except DBAPIError as e:
        if _is_retryable_database_error(e):
            raise RetryableArchiveCleanupError(
                "temporary database failure during archive cleanup"
            ) from e

        raise

    finally:
        try:
            await redis.aclose()
        finally:
            await engine.dispose()

@celery_app.task(
    name="maintenance.cleanup_expired_archives",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(RetryableArchiveCleanupError, RedisError),
    retry_backoff=10,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def cleanup_expired_archives(
    batch_size: int = 100,
    max_batches: int = 20,
) -> dict[str, int]:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")

    if not 1 <= max_batches <= 100:
        raise ValueError("max_batches must be between 1 and 100")

    return asyncio.run(
        _cleanup_expired_archives(
            batch_size=batch_size,
            max_batches=max_batches,
        )
    )


async def _publish_pending_cache_invalidations(batch_size: int) -> dict[str, int]:
    engine = get_engine()
    uow_factory = get_uow_factory(get_async_session_maker())
    redis = get_redis()
    invalidator = CacheInvalidator(redis=redis)
    publisher = OutboxPublisher(
        uow_factory,
        {
            CACHE_INVALIDATION_EVENT_TYPE: CacheInvalidationHandler(invalidator),
        },
    )
    try:
        published = await publisher.publish_pending(limit=batch_size)
        logger.info("pending cache invalidation finished: published=%s", published)
        return {"published": published}
    except DBAPIError as error:
        if _is_retryable_database_error(error):
            raise RetryableArchiveCleanupError(
                "temporary database failure during pending cache invalidation"
            ) from error
        raise
    finally:
        try:
            await redis.aclose()
        finally:
            await engine.dispose()


@celery_app.task(
    name="maintenance.publish_pending_cache_invalidations",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(RetryableArchiveCleanupError, RedisError),
    retry_backoff=10,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def publish_pending_cache_invalidations(batch_size: int = 100) -> dict[str, int]:
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    return asyncio.run(_publish_pending_cache_invalidations(batch_size))


async def _cleanup_stale_user_sessions(
    batch_size: int,
    max_batches: int,
    retention_days: int,
) -> dict[str, int]:
    engine = get_engine()
    uow_factory = get_uow_factory(get_async_session_maker())
    totals = {"sessions": 0, "batches": 0}
    cutoff = utcnow() - timedelta(days=retention_days)

    try:
        for _ in range(max_batches):
            async with uow_factory() as uow:
                # не держим воркер долго (тяжелый запрос/занятая строка)
                await uow.session.execute(
                    text("SET LOCAL lock_timeout = '5s'")
                )
                await uow.session.execute(
                    text("SET LOCAL statement_timeout = '60s'")
                )

                deleted = await uow.auth_repo.delete_stale_sessions(
                    cutoff=cutoff,
                    limit=batch_size,
                )

                if not deleted:
                    break

                await uow.commit()

            totals["sessions"] += deleted
            totals["batches"] += 1

            logger.info("user sessions cleanup batch: sessions=%s", deleted)

            if deleted < batch_size:
                break
        logger.info("user sessions cleanup finished: %s", totals)
        return totals
    except DBAPIError as e:
        if _is_retryable_database_error(e):
            raise RetryableArchiveCleanupError(
                "temporary database failure during user sessions cleanup"
            ) from e

        raise

    finally:
        await engine.dispose()


@celery_app.task(
    name="maintenance.cleanup_stale_user_sessions",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(RetryableArchiveCleanupError,),
    retry_backoff=10,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def cleanup_stale_user_sessions(
    batch_size: int = 1000,
    max_batches: int = 20,
    retention_days: int = 7,
) -> dict[str, int]:
    if not 1 <= batch_size <= 5000:
        raise ValueError("batch_size must be between 1 and 5000")

    if not 1 <= max_batches <= 100:
        raise ValueError("max_batches must be between 1 and 100")

    if not 1 <= retention_days <= 365:
        raise ValueError("retention_days must be between 1 and 365")

    return asyncio.run(
        _cleanup_stale_user_sessions(
            batch_size=batch_size,
            max_batches=max_batches,
            retention_days=retention_days,
        )
    )
