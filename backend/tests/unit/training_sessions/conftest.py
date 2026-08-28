import pytest
from fastapi import FastAPI

from app.auth.deps import get_current_user, get_optional_current_user
from app.training_sessions.deps import get_training_session_service


@pytest.fixture(autouse=True)
def override_training_session_route_dependencies(
    app: FastAPI,
    current_user,
    optional_current_user,
    training_session_service,
):
    async def provide_current_user():
        return current_user

    async def provide_optional_current_user():
        return optional_current_user

    async def provide_training_session_service():
        return training_session_service

    overrides = {
        get_current_user: provide_current_user,
        get_optional_current_user: provide_optional_current_user,
        get_training_session_service: provide_training_session_service,
    }
    app.dependency_overrides.update(overrides)

    yield

    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)
