import pytest
from datetime import UTC, datetime
from unittest.mock import Mock, create_autospec

from app.redis.service import RedisCacheService
from app.redis.invalidation import CacheInvalidator
from app.decks.repository import DeckRepository
from app.service import UnitOfWork
from app.users.repository import UserRepository, UserSettingsRepository
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
    unit.deck_repo.get_all_by_user_id.return_value = []
    return unit


@pytest.fixture
def users_cache():
    return create_autospec(RedisCacheService, instance=True)


@pytest.fixture
def users_invalidator():
    return create_autospec(CacheInvalidator, instance=True)


@pytest.fixture
def users_uow_factory(request):
    return Mock(side_effect=lambda: request.getfixturevalue("users_uow"))


@pytest.fixture
def users_domain_service(users_uow_factory, users_cache, users_invalidator):
    return UserService(
        uow_factory=users_uow_factory,
        cache_service=users_cache,
        cache_invalidator=users_invalidator,
    )


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
