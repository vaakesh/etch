import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app

@pytest.fixture(scope="function")
def app() -> FastAPI:
    app = create_app()
    return app

@pytest_asyncio.fixture(scope="function")
async def client(app: FastAPI):
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="https://test",
    ) as ac:
        yield ac