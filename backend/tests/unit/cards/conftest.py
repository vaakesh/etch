import pytest
from fastapi import FastAPI

from app.auth.deps import get_current_user
from app.cards.deps import get_card_service


@pytest.fixture(autouse=True)
def override_card_route_dependencies(
    app: FastAPI,
    current_user,
    card_service,
):
    async def provide_current_user():
        return current_user

    async def provide_card_service():
        return card_service

    overrides = {
        get_current_user: provide_current_user,
        get_card_service: provide_card_service,
    }
    app.dependency_overrides.update(overrides)

    yield

    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)
