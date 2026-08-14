import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import app.models  # noqa: F401 # sqlalchemy models registration
from app.auth.router import router as auth_router
from app.bff.router import router as bff_router
from app.cards.router import router as cards_router
from app.decks.router import router as decks_router
from app.exception_handlers import register_exception_handlers
from app.logging_config import (
    bind_request_context,
    format_http_status,
    format_log_value,
    format_query_string,
    mark_exception_as_logged,
    reset_request_context,
    setup_logging,
)
from app.redis.deps import get_redis
from app.training_sessions.router import router as training_sessions_router
from app.users.router import router as users_router
from fastapi import FastAPI, Request, Response



@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = get_redis()
    setup_logging(
        use_colors=True,
        log_sql=True,
        log_sql_parameters=False,
        slow_query_ms=200,
    )

    yield

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

    return app

app = create_app(lifespan=lifespan)

logger = logging.getLogger(__name__)

@app.middleware("http")
async def timing_middleware(
    request: Request, 
    call_next: Callable[[Request], Awaitable[Response]]
):
    context, context_token = bind_request_context(
        received_request_id=request.headers.get("X-Request-ID"),
        method=request.method,
        path=request.url.path,
    )
    query_string = format_query_string(request.url.query)
    client = (
        f"{request.client.host}:{request.client.port}"
        if request.client
        else "-"
    )
    start = time.perf_counter()
    try:
        logger.info(
            "HTTP request started\n"
            "  method: %s\n"
            "  path: %s\n"
            "  query: %s\n"
            "  client: %s",
            context.method,
            context.path,
            query_string,
            format_log_value(client, max_length=200),
        )
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        mark_exception_as_logged(exc)
        logger.exception(
            "HTTP request failed\n"
            "  method: %s\n"
            "  path: %s\n"
            "  status: 500 Internal Server Error\n"
            "  duration_ms: %.2f\n"
            "  error_type: %s\n"
            "  error_message: %s",
            context.method,
            context.path,
            duration_ms,
            type(exc).__name__,
            format_log_value(str(exc)),
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = context.request_id
        if response.status_code >= 500:
            log_level = logging.ERROR
            outcome = "server_error"
        elif response.status_code >= 400:
            log_level = logging.WARNING
            outcome = "client_error"
        elif duration_ms >= 500:
            log_level = logging.WARNING
            outcome = "slow"
        else:
            log_level = logging.INFO
            outcome = "success"

        logger.log(
            log_level,
            "HTTP request completed\n"
            "  method: %s\n"
            "  path: %s\n"
            "  status: %s\n"
            "  outcome: %s\n"
            "  duration_ms: %.2f",
            context.method,
            context.path,
            format_http_status(response.status_code),
            outcome,
            duration_ms,
        )
        return response
    finally:
        reset_request_context(context_token)
