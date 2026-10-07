import atexit
import logging
import os

from celery import current_task, signals
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.resources import Resource

from app.telemetry import setup_otel_logging, shutdown_otel_logging


_provider: LoggerProvider | None = None
_handler: LoggingHandler | None = None


class CeleryLogContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Ошибки самого экспортера оставляем в консоли.
        # Отправка их через тот же экспортер может создать цикл.
        if (
            record.name == "opentelemetry"
            or record.name.startswith("opentelemetry.")
        ):
            return False

        # Эти поля будут доступны в Loki как атрибуты записи.
        if current_task and current_task.request.id:
            record.task_id = current_task.request.id
            record.task_name = current_task.name
            record.task_retries = current_task.request.retries

        return True


@signals.after_setup_logger.connect(weak=False)
def configure_otel_logging(**kwargs) -> None:
    global _provider, _handler

    if _provider is not None:
        return

    resource = Resource.create(
        {
            "service.name": os.getenv(
                "OTEL_SERVICE_NAME",
                "etch-worker",
            ),
        },
    )

    _provider, _handler = setup_otel_logging(
        resource=resource,
        logger_name="",
    )
    _handler.addFilter(CeleryLogContextFilter())

    logging.getLogger(__name__).info(
        "Celery OTLP logging is ready",
        extra={"event": "telemetry.ready"},
    )


@signals.after_setup_task_logger.connect(weak=False)
def configure_task_logging(
    logger: logging.Logger,
    **kwargs,
) -> None:
    # Направляем сообщения celery.task в общий root logger.
    # Его обработчики обеспечат вывод в консоль и экспорт OTLP.
    logger.handlers.clear()
    logger.propagate = True


@signals.worker_process_shutdown.connect(weak=False)
@signals.worker_shutdown.connect(weak=False)
def stop_otel_logging(**kwargs) -> None:
    global _provider, _handler

    if _provider is None or _handler is None:
        return

    provider, handler = _provider, _handler
    _provider = None
    _handler = None

    shutdown_otel_logging(
        provider=provider,
        handler=handler,
        logger_name="",
    )


# Нормальное завершение отдельного Beat и других процессов.
atexit.register(stop_otel_logging)
