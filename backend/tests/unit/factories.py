from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

from app.training_sessions.models import TrainingSessionStatus

TEST_USER_UUID = UUID(
    "0198ad01-b200-7000-8000-000000000042"
)

def make_user(**overrides):
    data = {
        "id": 42,
        "uuid": TEST_USER_UUID,
        "username": "test-user",
        "email": "test@example.com",
        "hashed_password": "hashed-test-password",
        "created_at": datetime(
            2026, 8, 15, 12, 0, tzinfo=UTC
        ),
        "updated_at": datetime(
            2026, 8, 15, 13, 0, tzinfo=UTC
        ),
        "cards": [],
        "decks": [],
        "training_sessions": [],
        "user_sessions": [],
        "settings": None,
    }

    data.update(overrides)

    return SimpleNamespace(**data)

def make_user_settings(**overrides):
    data = {
        "locale": "ru-RU",
        "theme": "system",
        "show_previews_for_long": True,
    }

    data.update(overrides)
    return SimpleNamespace(**data)



TEST_CARD_UUID = UUID(
    "0198ad01-b200-7000-8000-000000000100"
)

def make_card(**overrides):
    data = {
        "id": 100,
        "uuid": TEST_CARD_UUID,
        "learning_key": TEST_CARD_UUID,
        "user_id": 42,
        "front_text": "привет",
        "back_text": "hello",
        "front_lang": "ru",
        "back_lang": "en",
        "created_at": datetime(
            2026, 8, 15, 14, 0, tzinfo=UTC,
        ),
        "updated_at": datetime(
            2026, 8, 15, 15, 0, tzinfo=UTC,
        ),
    }

    data.update(overrides)
    return SimpleNamespace(**data)



TEST_DECK_UUID = UUID(
    "0198ad01-b200-7000-8000-000000000200"
)
TEST_DECK_CARD_UUID = UUID(
    "0198ad01-b200-7000-8000-000000000300"
)

def make_deck(**overrides):
    user = overrides.pop("user", None) or make_user()

    data = {
        "id": 200,
        "uuid": TEST_DECK_UUID,
        "user_id": user.id,
        "state": "active",
        "archived_at": None,
        "expires_at": None,
        "archive_reason": None,
        "source_deck_uuid_snapshot": None,
        "title": "Test deck",
        "description": "Test deck description",
        "words_count": 10,
        "is_public": True,
        "saves_count": 5,
        "version": 1,
        "created_at": datetime(
            2026, 8, 15, 14, 0, tzinfo=UTC,
        ),
        "updated_at": datetime(
            2026, 8, 15, 15, 0, tzinfo=UTC,
        ),

        "user": user,
    }

    data.update(overrides)

    deck = SimpleNamespace(**data)

    deck.owner_uuid = user.uuid
    deck.owner_username = user.username

    return deck

def make_deck_card(**overrides):
    data = {
        "id": 300,
        "uuid": TEST_DECK_CARD_UUID,
        "deck_id": 200,
        "card_id": 100,
        "position": 1,
        "created_at": datetime(
            2026, 8, 15, 14, 0, tzinfo=UTC,
        ),
        "updated_at": datetime(
            2026, 8, 15, 15, 0, tzinfo=UTC,
        ),
    }

    data.update(overrides)
    return SimpleNamespace(**data)

def make_user_deck(**overrides):
    data = {
        "user_id": 42,
        "deck_id": 200,
        "sessions_count": 0,
        "correct_count": 0,
        "wrong_count": 0,
        "last_studied_at": None,
        "is_favourite": False,
        "is_saved": False,
        "last_seen_version": 1,
        "added_at": datetime(
            2026, 8, 15, 14, 0, tzinfo=UTC,
        ),
    }

    data.update(overrides)
    return SimpleNamespace(**data)



TEST_TRAINING_SESSION_UUID = UUID(
    "0198ad01-b200-7000-8000-000000000400"
)
TEST_TRAINING_SESSION_ITEM_UUID = UUID(
    "0198ad01-b200-7000-8000-000000000500"
)

def make_training_session(**overrides):
    deck = overrides.pop("deck") if "deck" in overrides else make_deck()

    data = {
        "id": 400,
        "uuid": TEST_TRAINING_SESSION_UUID,
        "user_id": 42,
        "deck_id": deck.id if deck is not None else None,
        "status": TrainingSessionStatus.IN_PROGRESS,
        "requested_count": 10,
        "answered_count": 3,
        "active_study_time_ms": 0,
        "activity_tracker_uuid": None,
        "activity_last_seen_at": None,
        "correct_count": 2,
        "wrong_count": 1,
        "prompt_side": "front",
        "answer_side": "back",
        "started_at": datetime(
            2026, 8, 15, 16, 0, tzinfo=UTC,
        ),
        "finished_at": None,
        "deck": deck,
        "items": [],
    }

    data.update(overrides)

    session = SimpleNamespace(**data)

    # Аналог TrainingSession.deck_uuid / deck_title properties
    session.deck_uuid = deck.uuid if deck is not None else None
    session.deck_title = deck.title if deck is not None else None

    return session

def make_training_session_item(**overrides):
    data = {
        "id": 500,
        "uuid": TEST_TRAINING_SESSION_ITEM_UUID,
        "training_session_id": 400,
        "sequence_number": 1,
        "original_card_id": 100,
        "user_typed_text": None,
        "prompt_text": "привет",
        "answer_text": "hello",
        "prompt_lang": "ru",
        "answer_lang": "en",
        "is_answered": False,
        "is_correct": None,
        "answered_at": None,
    }

    data.update(overrides)

    return SimpleNamespace(**data)



TEST_USER_SESSION_UUID = UUID(
    "ffffffff-ffff-ffff-ffff-ffffffffffff"
)
TEST_ACCESS_TOKEN = "test-access-token"
TEST_REFRESH_TOKEN = "test-refresh-token"

def make_user_session(**overrides):
    data = {
        "id": 600,
        "uuid": TEST_USER_SESSION_UUID,
        "user_id": 42,
        "refresh_token_hash": "test-refresh-token-hash",
        "user_agent": "pytest",
        "ip": "127.0.0.1",
        "expires_at": datetime(
            2026, 8, 20, 12, 0, tzinfo=UTC,
        ),
        "created_at": datetime(
            2026, 8, 15, 12, 0, tzinfo=UTC,
        ),
        "updated_at": datetime(
            2026, 8, 15, 12, 0, tzinfo=UTC,
        ),
        "revoked_at": None,
        "replaced_by_session_id": None,
    }

    data.update(overrides)
    return SimpleNamespace(**data)


def make_token_pair(**overrides):
    data = {
        "access_token": TEST_ACCESS_TOKEN,
        "refresh_token": TEST_REFRESH_TOKEN,
    }

    data.update(overrides)
    return SimpleNamespace(**data)
