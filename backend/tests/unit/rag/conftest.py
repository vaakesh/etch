from unittest.mock import create_autospec

import pytest

from app.rag.client import RagClient
from app.rag.deps import get_rag_client


@pytest.fixture
def rag_client():
    return create_autospec(RagClient, instance=True)


@pytest.fixture
def app(app, rag_client):
    app.dependency_overrides[get_rag_client] = lambda: rag_client
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_rag_client, None)
