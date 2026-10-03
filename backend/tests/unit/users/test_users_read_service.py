import pytest

from app.redis.schemas import CacheLookupResult
from app.users.errors import UserNotFoundError
from app.users.schemas import InternalUser, InternalUserSettings
from tests.unit.users.cases import (
    SETTINGS_DATA, USER_DATA, USER_UUID, USER_WITH_SETTINGS_DATA,
)


class TestGetByUuid:
    async def test_returns_cached_user_without_opening_uow(
        self, users_domain_service, users_cache, users_uow_factory,
    ):
        cached = InternalUser(**USER_DATA)
        users_cache.get_cached_users_by_uuids.return_value = CacheLookupResult(
            cached={USER_UUID: cached}, missing=[],
        )

        result = await users_domain_service.get_by_uuid(USER_UUID)

        assert result is cached
        assert result.model_dump(mode="json") == USER_DATA
        users_cache.get_cached_users_by_uuids.assert_awaited_once_with(user_uuids=[USER_UUID])
        users_uow_factory.assert_not_called()
        users_cache.cache_users.assert_not_awaited()

    async def test_loads_and_caches_user_on_cache_miss(
        self, users_domain_service, users_cache, users_uow, users_entity,
    ):
        users_cache.get_cached_users_by_uuids.return_value = CacheLookupResult(
            cached={}, missing=[USER_UUID],
        )
        users_uow.user_repo.get_by_uuid.return_value = users_entity

        result = await users_domain_service.get_by_uuid(USER_UUID)

        assert result.model_dump(mode="json") == USER_DATA
        users_uow.user_repo.get_by_uuid.assert_awaited_once_with(
            user_uuid=USER_UUID, for_update=False, include_settings=False,
        )
        users_cache.cache_users.assert_awaited_once_with(users=[result])
        users_cache.cache_users_settings.assert_not_awaited()
        users_uow.commit.assert_not_awaited()

    async def test_raises_not_found_without_caching(
        self, users_domain_service, users_cache, users_uow,
    ):
        users_cache.get_cached_users_by_uuids.return_value = CacheLookupResult(
            cached={}, missing=[USER_UUID],
        )
        users_uow.user_repo.get_by_uuid.return_value = None

        with pytest.raises(UserNotFoundError, match=f"User with uuid={USER_UUID} not found"):
            await users_domain_service.get_by_uuid(USER_UUID)

        users_cache.cache_users.assert_not_awaited()
        users_uow.commit.assert_not_awaited()


class TestGetByUuidWithSettings:
    async def test_returns_both_cached_parts_without_opening_uow(
        self, users_domain_service, users_cache, users_uow_factory,
    ):
        users_cache.get_cached_users_by_uuids.return_value = CacheLookupResult(
            cached={USER_UUID: InternalUser(**USER_DATA)}, missing=[],
        )
        users_cache.get_cached_users_settings.return_value = CacheLookupResult(
            cached={42: InternalUserSettings(**SETTINGS_DATA)}, missing=[],
        )

        result = await users_domain_service.get_by_uuid_with_settings(USER_UUID)

        assert result.model_dump(mode="json") == USER_WITH_SETTINGS_DATA
        users_cache.get_cached_users_by_uuids.assert_awaited_once_with(user_uuids=[USER_UUID])
        users_cache.get_cached_users_settings.assert_awaited_once_with(user_ids=[42])
        users_uow_factory.assert_not_called()
        users_cache.cache_users.assert_not_awaited()
        users_cache.cache_users_settings.assert_not_awaited()

    @pytest.mark.parametrize("cached_user", [False, True], ids=["user_miss", "settings_miss"])
    async def test_loads_and_caches_both_parts_on_partial_or_total_miss(
        self, users_domain_service, users_cache, users_uow, users_entity, cached_user,
    ):
        users_cache.get_cached_users_by_uuids.return_value = CacheLookupResult(
            cached={USER_UUID: InternalUser(**{**USER_DATA, "username": "stale-user"})} if cached_user else {},
            missing=[] if cached_user else [USER_UUID],
        )
        users_cache.get_cached_users_settings.return_value = CacheLookupResult(
            cached={}, missing=[42],
        )
        users_uow.user_repo.get_by_uuid.return_value = users_entity

        result = await users_domain_service.get_by_uuid_with_settings(USER_UUID)

        assert result.model_dump(mode="json") == USER_WITH_SETTINGS_DATA
        users_uow.user_repo.get_by_uuid.assert_awaited_once_with(
            user_uuid=USER_UUID, for_update=False, include_settings=True,
        )
        assert users_cache.cache_users.await_args.kwargs["users"][0].model_dump(mode="json") == USER_DATA
        users_cache.cache_users.assert_awaited_once()
        users_cache.cache_users_settings.assert_awaited_once_with(users_settings=[result.settings])
        if cached_user:
            users_cache.get_cached_users_settings.assert_awaited_once_with(user_ids=[42])
        else:
            users_cache.get_cached_users_settings.assert_not_awaited()
        users_uow.commit.assert_not_awaited()

    @pytest.mark.parametrize("cached_user", [False, True], ids=["user_miss", "settings_miss"])
    async def test_raises_not_found_when_user_disappears(
        self, users_domain_service, users_cache, users_uow, cached_user,
    ):
        users_cache.get_cached_users_by_uuids.return_value = CacheLookupResult(
            cached={USER_UUID: InternalUser(**USER_DATA)} if cached_user else {},
            missing=[] if cached_user else [USER_UUID],
        )
        users_cache.get_cached_users_settings.return_value = CacheLookupResult(cached={}, missing=[42])
        users_uow.user_repo.get_by_uuid.return_value = None

        with pytest.raises(UserNotFoundError):
            await users_domain_service.get_by_uuid_with_settings(USER_UUID)

        users_cache.cache_users.assert_not_awaited()
        users_cache.cache_users_settings.assert_not_awaited()


class TestGetUserProfile:
    @pytest.mark.parametrize(
        ("viewer_id", "expected_count"),
        [(42, 9), (7, 3), (None, 3)],
        ids=["owner", "other_user", "anonymous"],
    )
    async def test_selects_visible_deck_count_without_exposing_private_fields(
        self, users_domain_service, users_uow, users_entity, users_cache,
        viewer_id, expected_count,
    ):
        users_uow.user_repo.get_user_profile.return_value = (users_entity, 9, 3, 15)

        result = await users_domain_service.get_user_profile(viewer_id=viewer_id, username="test-user")

        assert result.model_dump(mode="json") == {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "test-user",
            "created_at": "2020-01-01T12:00:00Z",
            "deck_count": expected_count,
            "total_saves_count": 15,
        }
        users_uow.user_repo.get_user_profile.assert_awaited_once_with(profile_username="test-user")
        users_uow.commit.assert_not_awaited()
        assert users_cache.mock_calls == []

    async def test_returns_zero_counts_for_user_without_decks(
        self, users_domain_service, users_uow, users_entity,
    ):
        users_uow.user_repo.get_user_profile.return_value = (users_entity, 0, 0, 0)

        result = await users_domain_service.get_user_profile(viewer_id=None, username="test-user")

        assert result.model_dump(mode="json") == {
            "uuid": "0198ad01-b200-7000-8000-000000000042",
            "username": "test-user",
            "created_at": "2020-01-01T12:00:00Z",
            "deck_count": 0,
            "total_saves_count": 0,
        }

    async def test_raises_when_profile_is_missing(self, users_domain_service, users_uow):
        users_uow.user_repo.get_user_profile.return_value = None

        with pytest.raises(UserNotFoundError, match="User not found"):
            await users_domain_service.get_user_profile(viewer_id=None, username="unknown")

        users_uow.commit.assert_not_awaited()
