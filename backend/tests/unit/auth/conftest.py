from types import SimpleNamespace

import pytest


@pytest.fixture
def client(client, override_cookie_token_config):
    client.headers["user-agent"] = "pytest-agent"
    return client


@pytest.fixture
def override_cookie_token_config(monkeypatch):
    async def run_in_threadpool_directly(func, *args, **kwargs):
        return func(*args, **kwargs)

    auth_tokens_service = SimpleNamespace(
        config=SimpleNamespace(
            access_token_expire_minutes=50,
            refresh_token_expire_days=7,
        )
    )
    monkeypatch.setattr(
        "app.auth.cookies.get_auth_tokens_service",
        lambda: auth_tokens_service,
    )
    monkeypatch.setattr(
        "fastapi.dependencies.utils.run_in_threadpool",
        run_in_threadpool_directly,
    )
