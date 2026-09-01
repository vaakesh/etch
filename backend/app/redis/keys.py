import hashlib
from uuid import UUID

import orjson
from app.common.types import NormalizedSearch
from app.redis.schemas import UserDeckIdentity

def make_user_cache_key(user_id: int) -> str:
    return f"user:{user_id}"

def make_user_uuid_cache_key(
    user_uuid: UUID,
) -> str:
    return f"user:id-by-uuid:{user_uuid}"

def make_user_settings_cache_key(
    user_id: int,
) -> str:
    return f"user:{user_id}:settings"

def make_deck_uuid_cache_key(deck_uuid: UUID) -> str:
    return f"deck:id-by-uuid:{deck_uuid}"

def make_deck_cache_key(deck_id: int) -> str:
    return f"deck:{deck_id}"

def make_card_uuid_cache_key(card_uuid: UUID) -> str:
    return f"card:id-by-uuid:{card_uuid}"

def make_card_cache_key(card_id: int) -> str:
    return f"card:{card_id}"

def make_deck_cards_cache_key(deck_id: int) -> str:
    return f"deck:{deck_id}:card-ids"

def make_user_deck_cache_key(
    identity: UserDeckIdentity,
) -> str:
    user_id, deck_id = identity
    return f"deck:user-deck:{user_id}:{deck_id}"

def make_library_deck_page_generation_cache_key(
    user_id: int,
) -> str:
    return f"library:{user_id}:decks:generation"

def make_library_cards_page_generation_cache_key(
    user_id: int,
) -> str:
    return f"library:{user_id}:cards:generation"

def make_library_cards_page_cache_key(
    user_id: int,
    generation: int,
    search_query: NormalizedSearch | None = None,
    cursor: str | None = None,
    limit: int = 50,
):
    fingerprint = hashlib.sha256(
        orjson.dumps(
            [
                search_query,
                cursor,
                limit,
            ]
        )
    ).hexdigest()

    key = f"library:{user_id}:cards:v{generation}:{fingerprint}"
    return key

def make_library_deck_page_cache_key(
    user_id: int,
    generation: int,
    search_query: NormalizedSearch | None = None,
    is_favourite: bool = False,
    cursor: str | None = None,
    limit: int = 50,
):
    fingerprint = hashlib.sha256(
        orjson.dumps(
            [
                search_query,
                is_favourite,
                cursor,
                limit,
            ]
        )
    ).hexdigest()

    key = f"library:{user_id}:decks:v{generation}:{fingerprint}"
    return key
