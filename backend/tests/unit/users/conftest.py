import pytest
from fastapi import FastAPI

from app.auth.deps import get_auth_service, get_current_user
from app.cards.deps import get_card_service
from app.decks.deps import get_deck_service, get_user_deck_service
from app.training_sessions.deps import get_training_session_service
from app.users.deps import get_user_service


@pytest.fixture(autouse=True)
def override_user_route_dependencies(
    app: FastAPI,
    current_user,
    auth_service,
    card_service,
    deck_service,
    training_session_service,
    user_deck_service,
    user_service,
):
    async def provide_current_user():
        return current_user

    async def provide_auth_service():
        return auth_service

    async def provide_card_service():
        return card_service

    async def provide_deck_service():
        return deck_service

    async def provide_training_session_service():
        return training_session_service

    async def provide_user_deck_service():
        return user_deck_service

    async def provide_user_service():
        return user_service

    overrides = {
        get_current_user: provide_current_user,
        get_auth_service: provide_auth_service,
        get_card_service: provide_card_service,
        get_deck_service: provide_deck_service,
        get_training_session_service: provide_training_session_service,
        get_user_deck_service: provide_user_deck_service,
        get_user_service: provide_user_service,
    }
    app.dependency_overrides.update(overrides)

    yield

    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)
