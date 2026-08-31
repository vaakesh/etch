from unittest.mock import AsyncMock, create_autospec

from fastapi import FastAPI
import pytest

from app.auth.deps import (
    get_current_user, 
    get_optional_current_user
)
from app.users.deps import get_user_service
from app.users.service import UserService
from app.training_sessions.deps import get_training_session_service
from app.training_sessions.service import TrainingSessionService
from tests.unit.factories import (
    make_training_session,
    make_training_session_item,
    make_user,
    make_user_settings,
)


from app.decks.deps import (
    get_deck_service,
    get_user_deck_service,
)
from app.decks.service import (
    DeckService,
    UserDeckService,
)
from app.redis.deps import get_redis_rate_limiter
from app.redis.service import RedisRateLimiter
from tests.unit.factories import (
    make_deck,
    make_deck_card,
    make_user_deck,
)


@pytest.fixture
def current_user(request):
    overrides = getattr(request, "param", {})
    return make_user(**overrides)

@pytest.fixture
def optional_current_user(
    request,
    current_user,
):
    return getattr(
        request,
        "param",
        current_user,
    )


@pytest.fixture
def redis_rate_limiter():
    rate_limiter = create_autospec(
        RedisRateLimiter,
        instance=True,
    )
    rate_limiter.check.return_value = True
    return rate_limiter


@pytest.fixture(autouse=True)
def override_redis_rate_limiter(
    app: FastAPI,
    redis_rate_limiter,
):
    async def provide_redis_rate_limiter():
        return redis_rate_limiter

    app.dependency_overrides[get_redis_rate_limiter] = provide_redis_rate_limiter

    yield

    app.dependency_overrides.pop(
        get_redis_rate_limiter,
        None,
    )

@pytest.fixture
def user_settings(request):
    overrides = getattr(request, "param", {})
    return make_user_settings(**overrides)

@pytest.fixture(autouse=True)
def override_current_users(
    app: FastAPI,
    current_user,
    optional_current_user,
):
    async def provide_current_user():
        return current_user

    async def provide_optional_current_user():
        return optional_current_user

    app.dependency_overrides[get_current_user] = provide_current_user
    app.dependency_overrides[
        get_optional_current_user
    ] = provide_optional_current_user

    yield

    app.dependency_overrides.pop(
        get_current_user,
        None,
    )
    app.dependency_overrides.pop(
        get_optional_current_user,
        None,
    )

@pytest.fixture
def user_service():
    return create_autospec(
        UserService,
        instance=True,
    )

@pytest.fixture(autouse=True)
def override_user_service(
    app: FastAPI,
    user_service: AsyncMock,
):
    app.dependency_overrides[get_user_service] = (
        lambda: user_service
    )

    yield

    app.dependency_overrides.pop(
        get_user_service,
        None,
    )


@pytest.fixture
def training_session(request):
    overrides = getattr(request, "param", {})
    return make_training_session(**overrides)

@pytest.fixture
def training_session_item(request):
    overrides = getattr(request, "param", {})
    return make_training_session_item(**overrides)

@pytest.fixture
def training_session_service():
    return create_autospec(
        TrainingSessionService,
        instance=True,
    )

@pytest.fixture(autouse=True)
def override_training_session_service(
    app: FastAPI,
    training_session_service,
):
    app.dependency_overrides[
        get_training_session_service
    ] = lambda: training_session_service

    yield

    app.dependency_overrides.pop(
        get_training_session_service,
        None,
    )


@pytest.fixture
def deck(request):
    overrides = getattr(request, "param", {})
    return make_deck(**overrides)


@pytest.fixture
def deck_card(request):
    overrides = getattr(request, "param", {})
    return make_deck_card(**overrides)


@pytest.fixture
def user_deck(request):
    overrides = getattr(request, "param", {})
    return make_user_deck(**overrides)


@pytest.fixture
def deck_service():
    return create_autospec(
        DeckService,
        instance=True,
    )


@pytest.fixture
def user_deck_service():
    return create_autospec(
        UserDeckService,
        instance=True,
    )


@pytest.fixture(autouse=True)
def override_deck_services(
    app: FastAPI,
    deck_service,
    user_deck_service,
):
    app.dependency_overrides[get_deck_service] = (
        lambda: deck_service
    )
    app.dependency_overrides[get_user_deck_service] = (
        lambda: user_deck_service
    )

    yield

    app.dependency_overrides.pop(
        get_deck_service,
        None,
    )
    app.dependency_overrides.pop(
        get_user_deck_service,
        None,
    )



import pytest

from app.cards.deps import get_card_service
from app.cards.service import CardService
from tests.unit.factories import make_card


@pytest.fixture
def card(request):
    overrides = getattr(request, "param", {})
    return make_card(**overrides)


@pytest.fixture
def card_service():
    return create_autospec(
        CardService,
        instance=True,
    )


@pytest.fixture(autouse=True)
def override_card_service(
    app: FastAPI,
    card_service,
):
    app.dependency_overrides[get_card_service] = (
        lambda: card_service
    )

    yield

    app.dependency_overrides.pop(
        get_card_service,
        None,
    )


import pytest

from app.auth.deps import get_auth_service
from app.auth.service import AuthService
from tests.unit.factories import (
    make_token_pair,
    make_user_session,
)


@pytest.fixture
def user_session(request):
    overrides = getattr(request, "param", {})
    return make_user_session(**overrides)


@pytest.fixture
def token_pair(request):
    overrides = getattr(request, "param", {})
    return make_token_pair(**overrides)


@pytest.fixture
def auth_service():
    return create_autospec(
        AuthService,
        instance=True,
    )


@pytest.fixture(autouse=True)
def override_auth_service(
    app: FastAPI,
    auth_service,
):
    app.dependency_overrides[get_auth_service] = (
        lambda: auth_service
    )

    yield

    app.dependency_overrides.pop(
        get_auth_service,
        None,
    )
