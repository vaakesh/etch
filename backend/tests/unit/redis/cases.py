from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.cards.schemas import InternalCard
from app.decks.schemas import InternalDeck, InternalUserDeck
from app.users.schemas import InternalUser, InternalUserSettings


USER_UUID = UUID("0198ad01-b200-7000-8000-000000000042")
CARD_UUID = UUID("0198ad01-b200-7000-8000-000000000100")
DECK_UUID = UUID("0198ad01-b200-7000-8000-000000000200")
OTHER_UUID = UUID("0198ad01-b200-7000-8000-000000000999")

USER_DATA = {
    "id": 42, "uuid": str(USER_UUID), "username": "test-user",
    "email": "test@example.com", "hashed_password": "hashed-test-password",
    "created_at": "2020-01-01T12:00:00Z", "updated_at": "2020-01-01T13:00:00Z",
}
CARD_DATA = {
    "id": 100, "uuid": str(CARD_UUID), "user_id": 42,
    "front_text": "привет", "back_text": "hello", "front_lang": "ru", "back_lang": "en",
    "created_at": "2020-01-01T12:00:00Z", "updated_at": "2020-01-01T13:00:00Z",
}
DECK_DATA = {
    "id": 200, "uuid": str(DECK_UUID), "user_id": 42,
    "owner_uuid": str(USER_UUID), "owner_username": "test-user", "title": "Test deck",
    "description": None, "words_count": 2, "is_public": True, "saves_count": 5, "version": 1,
    "created_at": "2020-01-01T12:00:00Z", "updated_at": "2020-01-01T13:00:00Z",
}
SETTINGS_DATA = {
    "user_id": 42, "locale": "ru-RU", "theme": "system", "show_previews_for_long": True,
    "created_at": "2020-01-01T12:00:00Z", "updated_at": "2020-01-01T13:00:00Z",
}
USER_DECK_DATA = {
    "user_id": 42, "deck_id": 200, "sessions_count": 0, "correct_count": 0,
    "wrong_count": 0, "last_studied_at": None, "is_favourite": False,
    "is_saved": True, "last_seen_version": 1, "added_at": "2020-01-01T12:00:00Z",
}


@dataclass(frozen=True)
class CacheCase:
    name: str
    cache_method: str
    cache_argument: str
    get_method: str
    get_argument: str
    key: str
    identity: int | tuple[int, int]
    payload: dict[str, Any] | list[int]
    ttl: int
    schema: type[BaseModel] | None = None
    uuid: UUID | None = None
    uuid_get_method: str | None = None
    uuid_key: str | None = None


CACHE_CASES = [
    CacheCase(
        "users", "cache_users", "users", "get_cached_users", "user_ids",
        "user:42", 42, USER_DATA, 10800, InternalUser, USER_UUID,
        "get_cached_users_by_uuids", f"user:id-by-uuid:{USER_UUID}",
    ),
    CacheCase(
        "cards", "cache_cards", "cards", "get_cached_cards", "card_ids",
        "card:100", 100, CARD_DATA, 1800, InternalCard, CARD_UUID,
        "get_cached_cards_by_uuids", f"card:id-by-uuid:{CARD_UUID}",
    ),
    CacheCase(
        "decks", "cache_decks", "decks", "get_cached_decks", "deck_ids",
        "deck:200", 200, DECK_DATA, 1800, InternalDeck, DECK_UUID,
        "get_cached_decks_by_uuids", f"deck:id-by-uuid:{DECK_UUID}",
    ),
    CacheCase(
        "settings", "cache_users_settings", "users_settings",
        "get_cached_users_settings", "user_ids", "user:42:settings",
        42, SETTINGS_DATA, 3600, InternalUserSettings,
    ),
    CacheCase(
        "user_decks", "cache_user_decks", "user_decks",
        "get_cached_user_decks", "deck_ids", "deck:user-deck:42:200",
        (42, 200), USER_DECK_DATA, 600, InternalUserDeck,
    ),
    CacheCase(
        "deck_cards", "cache_deck_cards", "deck_cards",
        "get_cached_deck_cards", "deck_ids", "deck:200:card-ids",
        200, [100, 101], 3600,
    ),
]
UUID_CASES = [case for case in CACHE_CASES if case.uuid is not None]


def cache_kwargs(case: CacheCase, *, empty: bool = False) -> dict:
    if case.schema is None:
        return {case.cache_argument: {} if empty else {case.identity: case.payload}}
    entities = [] if empty else [case.schema.model_validate(case.payload)]
    kwargs = {case.cache_argument: entities}
    if case.name == "user_decks":
        kwargs["user_id"] = 42
    return kwargs


def get_kwargs(case: CacheCase, *, empty: bool = False) -> dict:
    identity = case.identity[1] if isinstance(case.identity, tuple) else case.identity
    kwargs = {case.get_argument: [] if empty else [identity]}
    if case.name == "user_decks":
        kwargs["user_id"] = 42
    return kwargs


def dump_cached(value):
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else value
