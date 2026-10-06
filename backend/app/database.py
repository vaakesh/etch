from functools import lru_cache

from app.config import get_settings
from app.tracing import traced
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


@lru_cache
@traced("database.get_engine")
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        url=settings.database_url(),
        echo=False,
    )

@lru_cache
def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
    )


class Base(DeclarativeBase):
    __abstract__ = True
