import app.models # noqa: F401 # sqlalchemy models registration
from contextlib import asynccontextmanager
import time
import logging
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response, logger
from app.users.router import router as users_router
from app.training_sessions.router import router as training_sessions_router
from app.cards.router import router as cards_router
from app.decks.router import router as decks_router
from app.auth.router import router as auth_router
from app.utils import format_duration
from app.logging_config import setup_logging
from app.exception_handlers import register_exception_handlers

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    yield


def create_app(*args, **kwargs) -> FastAPI:
    app = FastAPI(*args, **kwargs)

    app.include_router(users_router)
    app.include_router(training_sessions_router)
    app.include_router(cards_router)
    app.include_router(decks_router)
    app.include_router(auth_router)
    
    register_exception_handlers(app)

    return app

app = create_app(lifespan=lifespan)

logger = logging.getLogger(__name__)

@app.middleware("http")
async def timing_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    logger.info(f"{request.method} {request.url.path} completed in {format_duration(duration)}"
                f" | status={response.status_code}")
    return response