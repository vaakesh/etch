from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app.auth.deps import get_auth_service, get_current_user


@pytest.fixture(autouse=True)
def override_auth_route_dependencies(
    app: FastAPI,
    current_user,
    auth_service,
):
    async def provide_current_user():
        return current_user

    async def provide_auth_service():
        return auth_service

    overrides = {
        get_current_user: provide_current_user,
        get_auth_service: provide_auth_service,
    }
    app.dependency_overrides.update(overrides)

    yield

    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)


@pytest.fixture(autouse=True)
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
