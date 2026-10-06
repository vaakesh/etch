from contextlib import asynccontextmanager

import app.models  # noqa: F401 # sqlalchemy models registration
from app.auth.router import router as auth_router
from app.bff.router import router as bff_router
from app.cards.router import router as cards_router
from app.decks.router import router as decks_router
from app.deps import require_metrics_access
from app.exception_handlers import register_exception_handlers
from app.logging_config import setup_logging
from app.middleware import setup_middlwares
from app.redis.deps import get_redis
from app.training_sessions.router import router as training_sessions_router
from app.users.router import router as users_router
from fastapi import Depends, FastAPI, Response
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = get_redis()
    setup_logging(
        use_colors=True,
        log_sql=False,
        log_sql_parameters=False,
        slow_query_ms=200,
    )

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    yield

    provider.shutdown()
    await redis.aclose()
    get_redis.cache_clear()


def create_app(*args, **kwargs) -> FastAPI:
    app = FastAPI(*args, **kwargs)

    app.include_router(users_router)
    app.include_router(training_sessions_router)
    app.include_router(cards_router)
    app.include_router(decks_router)
    app.include_router(auth_router)
    app.include_router(bff_router)

    register_exception_handlers(app)
    setup_middlwares(app)

    return app


app = create_app(lifespan=lifespan)


@app.get(
    "/metrics",
    include_in_schema=True,
    dependencies=[Depends(require_metrics_access)],
)
def get_metrics():
    return Response(
        content=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )
