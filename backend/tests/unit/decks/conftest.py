import pytest
from fastapi import FastAPI

from app.auth.deps import get_current_user, get_optional_current_user
from app.cards.deps import get_card_service
from app.decks.deps import get_deck_service, get_user_deck_service


@pytest.fixture(autouse=True)
def override_deck_route_dependencies(
    app: FastAPI,
    current_user,
    optional_current_user,
    card_service,
    deck_service,
    user_deck_service,
):
    async def provide_current_user():
        return current_user

    async def provide_optional_current_user():
        return optional_current_user

    async def provide_card_service():
        return card_service

    async def provide_deck_service():
        return deck_service

    async def provide_user_deck_service():
        return user_deck_service

    overrides = {
        get_current_user: provide_current_user,
        get_optional_current_user: provide_optional_current_user,
        get_card_service: provide_card_service,
        get_deck_service: provide_deck_service,
        get_user_deck_service: provide_user_deck_service,
    }
    app.dependency_overrides.update(overrides)

    yield

    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)
