from types import SimpleNamespace
from unittest.mock import create_autospec

from fastapi import FastAPI
import pytest

from app.auth.deps import (
    get_auth_service,
    get_captcha_service,
    get_current_user,
    get_current_user_with_settings,
    get_optional_current_user,
)
from app.auth.service import AuthService, CaptchaService
from app.bff.deps import get_bff_service
from app.cards.deps import get_card_service
from app.cards.service import CardService
from app.decks.deps import get_deck_service, get_user_deck_service
from app.decks.service import DeckService, UserDeckService
from app.redis.deps import get_redis_rate_limiter
from app.redis.service import RedisRateLimiter
from app.training_sessions.deps import get_training_session_service
from app.training_sessions.service import TrainingSessionService
from app.users.deps import get_user_service
from app.users.service import UserService
from tests.unit.factories import (
    make_card,
    make_deck,
    make_deck_card,
    make_token_pair,
    make_training_session,
    make_training_session_item,
    make_user,
    make_user_deck,
    make_user_session,
    make_user_settings,
)


@pytest.fixture
def app(app: FastAPI, request):
    def provide_fixture(fixture_name):
        async def provide():
            # Resolve mocks only when the route requests this dependency.
            return request.getfixturevalue(fixture_name)

        return provide

    dependencies = {
        get_current_user: "current_user",
        get_optional_current_user: "optional_current_user",
        get_current_user_with_settings: "current_user_with_settings",
        get_redis_rate_limiter: "redis_rate_limiter",
        get_auth_service: "auth_service",
        get_captcha_service: "captcha_service",
        get_bff_service: "bff_service",
        get_card_service: "card_service",
        get_deck_service: "deck_service",
        get_user_deck_service: "user_deck_service",
        get_training_session_service: "training_session_service",
        get_user_service: "user_service",
    }
    app.dependency_overrides.update({
        dependency: provide_fixture(fixture_name)
        for dependency, fixture_name in dependencies.items()
    })

    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def current_user(request):
    overrides = getattr(request, "param", {})
    return make_user(**overrides)


@pytest.fixture
def optional_current_user(request):
    if hasattr(request, "param"):
        return request.param
    return request.getfixturevalue("current_user")


@pytest.fixture
def redis_rate_limiter():
    rate_limiter = create_autospec(RedisRateLimiter, instance=True)
    rate_limiter.check.return_value = True
    return rate_limiter


@pytest.fixture
def user_settings(request):
    overrides = getattr(request, "param", {})
    return make_user_settings(**overrides)


@pytest.fixture
def current_user_with_settings(current_user, user_settings):
    return SimpleNamespace(**{**vars(current_user), "settings": user_settings})


@pytest.fixture
def user_service():
    return create_autospec(UserService, instance=True)


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
    return create_autospec(TrainingSessionService, instance=True)


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
    return create_autospec(DeckService, instance=True)


@pytest.fixture
def user_deck_service():
    return create_autospec(UserDeckService, instance=True)


@pytest.fixture
def card(request):
    overrides = getattr(request, "param", {})
    return make_card(**overrides)


@pytest.fixture
def card_service():
    return create_autospec(CardService, instance=True)


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
    return create_autospec(AuthService, instance=True)


@pytest.fixture
def captcha_service():
    return create_autospec(CaptchaService, instance=True)
