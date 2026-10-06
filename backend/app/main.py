import asyncio
from contextlib import asynccontextmanager
import logging

import app.models  # noqa: F401 # sqlalchemy models registration
from app.auth.router import router as auth_router
from app.bff.router import router as bff_router
from app.cards.router import router as cards_router
from app.decks.router import router as decks_router
from app.deps import require_metrics_access
from app.exception_handlers import register_exception_handlers
from app.health import router as health_router
from app.logging_config import setup_logging
from app.middleware import setup_middlewares
from app.redis.deps import get_redis
from app.training_sessions.router import router as training_sessions_router
from app.users.router import router as users_router
from fastapi import Depends, FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.telemetry import (
    get_trace_provider,
    setup_otel_logging,
    setup_tracing,
    shutdown_otel_logging,
    shutdown_tracing,
)
from app.tracing import traced

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(
        use_colors=True,
        log_sql=False,
        log_sql_parameters=False,
        slow_query_ms=200,
    )

    trace_provider = setup_tracing()
    redis = get_redis()

    log_provider, log_handler = setup_otel_logging(
        resource=trace_provider.resource,
    )

    try:
        logging.getLogger("app.startup").info(
            "OTLP logging is ready",
            extra={"event": "telemetry.ready"},
        )
        yield
    finally:
        try:
            try:
                await redis.aclose()
            finally:
                get_redis.cache_clear()
        finally:
            try:
                await asyncio.to_thread(shutdown_tracing, trace_provider)
            finally:
                await asyncio.to_thread(
                    shutdown_otel_logging,
                    log_provider,
                    log_handler,
                )


def create_app(*args, **kwargs) -> FastAPI:
    app = FastAPI(*args, **kwargs)

    app.include_router(users_router)
    app.include_router(training_sessions_router)
    app.include_router(cards_router)
    app.include_router(decks_router)
    app.include_router(auth_router)
    app.include_router(bff_router)
    app.include_router(health_router)

    register_exception_handlers(app)
    setup_middlewares(app)

    return app


app = create_app(lifespan=lifespan)
FastAPIInstrumentor.instrument_app(
    app,
    exclude_spans=["receive", "send"],
)

@app.get(
    "/metrics",
    include_in_schema=True,
    dependencies=[Depends(require_metrics_access)],
)
@traced("metrics.router.get_metrics")
def get_metrics():
    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )
