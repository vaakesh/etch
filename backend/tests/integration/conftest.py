from httpx import ASGITransport, AsyncClient
import pytest_asyncio
import pytest

from app.main import create_app



@pytest.fixture
def test_app():
    app = create_app()
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)

    async with AsyncClient(
        transport=transport,
        base_url="https://test",
    ) as client:
        yield client
