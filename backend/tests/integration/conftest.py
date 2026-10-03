from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from itertools import count
import logging

from httpx import ASGITransport, AsyncClient
import pytest_asyncio
import pytest
from redis.asyncio import Redis
from sqlalchemy import NullPool, text
from fastapi import FastAPI, status
import app.models  # noqa: F401 # sqlalchemy models registration
from app.main import create_app
from app.config import Settings, get_settings
from app.redis.deps import get_redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import (
    Base,
    get_async_session_maker,
    get_engine,
)

logger = logging.getLogger(__name__)
TEST_DB_NAME = "etch_test_integration"

@pytest.fixture(scope="session")
def settings():
    settings = get_settings()
    if settings.db_name != TEST_DB_NAME:
        pytest.exit(
            f"Tests aborted: wrong database configured: got \"{settings.db_name}\", expected \"{TEST_DB_NAME}\""
        )
    logger.debug("test database verified: %s", settings.db_name)
    yield settings

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(settings: Settings):
    logger.debug("creating database engine")
    engine = create_async_engine(
        url=settings.database_url(),
        echo=False,
        poolclass=NullPool,
    )
    yield engine
    logger.debug("disposing database engine")
    await engine.dispose()


async def truncate_database(engine: AsyncEngine) -> None:
    preparer = engine.dialect.identifier_preparer
    tables = ", ".join(
        preparer.format_table(table)
        for table in Base.metadata.tables.values()
    )

    async with engine.begin() as connection:
        await connection.execute(
            text(f"TRUNCATE TABLE {tables} RESTART IDENTITY")
        )


@pytest_asyncio.fixture(
    scope="function",
    loop_scope="session",
    autouse=True,
)
async def clean_database(engine: AsyncEngine) -> AsyncIterator[None]:
    logger.debug("clearing database before test")
    await truncate_database(engine)

    try:
        yield
    finally:
        logger.debug("clearing database after test")
        await truncate_database(engine)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def redis_client() -> AsyncIterator[Redis]:
    logger.debug("creating redis client")
    redis = get_redis()
    try:
        yield redis
    finally:
        logger.debug("closing redis client")
        await redis.aclose()
        get_redis.cache_clear()


async def flush_redis(redis_client: Redis) -> None:
    await redis_client.execute_command("FLUSHDB", "SYNC")


@pytest_asyncio.fixture(
    scope="function",
    loop_scope="session",
    autouse=True,
)
async def clean_redis(redis_client: Redis) -> AsyncIterator[None]:
    logger.debug("clearing redis database before test")
    await flush_redis(redis_client)

    try:
        yield
    finally:
        logger.debug("clearing redis database after test")
        await flush_redis(redis_client)


@pytest.fixture(scope="session")
def async_session_maker(engine: AsyncEngine):
    async_session_maker = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    logger.debug("async database session factory created")
    return async_session_maker

@pytest.fixture(scope="session")
def app(
    settings: Settings,
    engine: AsyncEngine,
    async_session_maker: async_sessionmaker[AsyncSession],
):
    logger.debug("creating test app")
    app = create_app()
    def provide_test_settings():
        return settings
    def provide_test_engine():
        return engine
    def provide_test_session_maker():
        return async_session_maker

    app.dependency_overrides[get_settings] = provide_test_settings
    app.dependency_overrides[get_engine] = provide_test_engine
    app.dependency_overrides[get_async_session_maker] = provide_test_session_maker
    logger.debug("test app dependency overrides configured")

    yield app
    logger.debug("clearing test app dependency overrides")
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def client(app: FastAPI):
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="https://test",
    ) as client:
        yield client

type ClientFactory = Callable[[], Awaitable[AsyncClient]]

@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def client_factory(
    app: FastAPI
) -> AsyncIterator[ClientFactory]:
    async with AsyncExitStack() as stack:

        async def make_client() -> AsyncClient:
            return await stack.enter_async_context(
                AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="https://test",
                )
            )

        yield make_client
