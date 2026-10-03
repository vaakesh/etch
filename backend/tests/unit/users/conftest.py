import pytest
from datetime import UTC, datetime
from unittest.mock import Mock, create_autospec
from fastapi import FastAPI

from app.auth.deps import get_auth_service, get_current_user
from app.cards.deps import get_card_service
from app.decks.deps import get_deck_service, get_user_deck_service
from app.training_sessions.deps import get_training_session_service
from app.users.deps import get_user_service
from app.redis.service import RedisCacheService
from app.service import UnitOfWork
from app.users.repository import UserRepository, UserSettingsRepository
from app.decks.repository import DeckRepository, UserDeckRepository
from app.users.service import UserService
from tests.unit.factories import make_user, make_user_settings


@pytest.fixture
def users_uow():
    unit = create_autospec(UnitOfWork, instance=True)
    unit.__aenter__.return_value = unit
    unit.__aexit__.return_value = False
    unit.user_repo = create_autospec(UserRepository, instance=True)
    unit.user_settings_repo = create_autospec(UserSettingsRepository, instance=True)
    unit.deck_repo = create_autospec(DeckRepository, instance=True)
    unit.user_deck_repo = create_autospec(UserDeckRepository, instance=True)
    return unit


@pytest.fixture
def users_cache():
    return create_autospec(RedisCacheService, instance=True)


@pytest.fixture
def users_uow_factory(users_uow):
    return Mock(return_value=users_uow)


@pytest.fixture
def users_domain_service(users_uow_factory, users_cache):
    return UserService(uow_factory=users_uow_factory, cache_service=users_cache)


@pytest.fixture
def users_entity():
    settings = make_user_settings(
        user_id=42,
        created_at=datetime(2020, 1, 1, 12, tzinfo=UTC),
        updated_at=datetime(2020, 1, 1, 13, tzinfo=UTC),
    )
    return make_user(
        created_at=datetime(2020, 1, 1, 12, tzinfo=UTC),
        updated_at=datetime(2020, 1, 1, 13, tzinfo=UTC),
        settings=settings,
    )


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
