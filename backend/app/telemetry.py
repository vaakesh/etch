import os
from functools import lru_cache

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import logging

from opentelemetry.exporter.otlp.proto.http._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

from app.logging_config import RequestContextFilter
from app.database import get_engine

def setup_otel_logging(
    resource: Resource,
    logger_name: str = "app",
) -> tuple[LoggerProvider, LoggingHandler]:
    provider = LoggerProvider(
        resource=resource,
        shutdown_on_exit=False,
    )

    exporter = OTLPLogExporter(timeout=5)

    processor = BatchLogRecordProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=1000,
    )
    provider.add_log_record_processor(processor)

    handler = LoggingHandler(
        level=logging.INFO,
        logger_provider=provider,
        log_code_attributes=True,
    )
    handler.addFilter(RequestContextFilter())

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = True
    logger.addHandler(handler)

    return provider, handler


def shutdown_otel_logging(
    provider: LoggerProvider,
    handler: LoggingHandler,
    logger_name: str = "app",
) -> None:
    logging.getLogger(logger_name).removeHandler(handler)

    try:
        provider.shutdown()
    finally:
        handler.close()


@lru_cache
def get_trace_provider() -> TracerProvider:
    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "etch-api"),
        }
    )

    provider = TracerProvider(
        resource=resource,
        shutdown_on_exit=False,
    )

    exporter = OTLPSpanExporter(
        timeout=5,
    )

    processor = BatchSpanProcessor(
        exporter,
        max_queue_size=2048,
        max_export_batch_size=512,
        schedule_delay_millis=5000,
    )

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    return provider


def setup_tracing() -> TracerProvider:
    provider = get_trace_provider()

    # SQLAlchemy covers asyncpg queries; instrumenting both duplicates SQL spans.
    SQLAlchemyInstrumentor().instrument(
        engine=get_engine().sync_engine,
        tracer_provider=provider,
    )
    RedisInstrumentor().instrument(
        tracer_provider=provider
    )

    return provider


def shutdown_tracing(provider: TracerProvider) -> None:
    try:
        SQLAlchemyInstrumentor().uninstrument()
        RedisInstrumentor().uninstrument()
    finally:
        provider.shutdown()
