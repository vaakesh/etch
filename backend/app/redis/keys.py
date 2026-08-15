import hashlib
from uuid import UUID

import orjson

from app.users.schemas import NormalizedSearch
from app.redis.schemas import UserDeckIdentity


def make_deck_cache_key(deck_uuid: UUID) -> str:
    return f"deck:{deck_uuid}"

def make_card_cache_key(card_uuid: UUID) -> str:
    return f"card:{card_uuid}"

def make_deck_cards_cache_key(deck_uuid: UUID) -> str:
    return f"deck:{deck_uuid}:card-uuids"

def make_user_deck_cache_key(
    identity: UserDeckIdentity,
) -> str:
    user_id, deck_id = identity
    return f"deck:user-deck:{user_id}:{deck_id}"

def make_library_deck_page_generation_cache_key(
    user_uuid: UUID,
) -> str:
    return f"library:{user_uuid}:decks:generation"

def make_library_cards_page_generation_cache_key(
    user_uuid: UUID,
) -> str:
    return f"library:{user_uuid}:cards:generation"

def make_library_cards_page_cache_key(
    user_uuid: UUID,
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

    key = f"library:{user_uuid}:cards:v{generation}:{fingerprint}"
    return key

def make_library_deck_page_cache_key(
    user_uuid: UUID,
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

    key = f"library:{user_uuid}:decks:v{generation}:{fingerprint}"
    return key