import app.celery.celery_logging  # noqa: F401 — регистрация сигналов логирования
from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

celery_app = Celery(
    "etch",
    broker=get_settings().celery_broker_url,
    include=["app.celery.tasks"],
)

celery_app.conf.update(
    task_default_queue="maintenance",
    task_ignore_result=True,
    control_queue_exclusive=True,
    event_queue_exclusive=True,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "publish-pending-cache-invalidations": {
            "task": "maintenance.publish_pending_cache_invalidations",
            "schedule": 30.0,
            "kwargs": {"batch_size": 100},
        },
        "cleanup-expired-archives-hourly": {
            "task": "maintenance.cleanup_expired_archives",
            "schedule": crontab(minute=0),
            "kwargs": {
                "batch_size": 100,
                "max_batches": 20,
            },
        },
        "cleanup-stale-user-sessions-hourly": {
            "task": "maintenance.cleanup_stale_user_sessions",
            "schedule": crontab(minute=30),
            "kwargs": {
                "batch_size": 1000,
                "max_batches": 20,
                "retention_days": 7,
            },
        },
    },
)
