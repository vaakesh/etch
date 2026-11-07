import logging
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.conftest import ClientFactory
from tests.integration.reviews.conftest import (
    create_deck,
    set_memory_due,
    start_review,
    study_deck,
)
from tests.integration.training_sessions.conftest import start_practice
from tests.integration.users.conftest import AuthClientFactory, UserFactory

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio(loop_scope="session")

EMPTY_SIDE = {"due_now": 0, "due_today": 0, "next_due_at": None}


def tokyo_end_of_day() -> datetime:
    # Полночь следующих суток в Asia/Tokyo, в UTC
    zone = ZoneInfo("Asia/Tokyo")
    tomorrow = datetime.now(zone).date() + timedelta(days=1)
    return datetime.combine(tomorrow, time(), tzinfo=zone).astimezone(UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class TestGetReviewSummary:
    async def test_returns_empty_summary_without_studied_words(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)

        response = await client.get("/bff/reviews/summary")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "timezone": "UTC",
            "sides": {"front": EMPTY_SIDE, "back": EMPTY_SIDE},
            "active_session": None,
        }

    async def test_counts_due_words_per_side_until_end_of_user_day(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        response = await client.patch(
            "/users/me/settings",
            json={"timezone": "Asia/Tokyo"},
        )
        assert response.status_code == status.HTTP_200_OK
        answers = {"кот": "cat", "пёс": "dog", "лис": "fox"}
        deck_uuid = await create_deck(client, "Animals", list(answers.items()))
        await study_deck(client, deck_uuid, "front", answers)
        await study_deck(client, deck_uuid, "back", {v: k for k, v in answers.items()})
        end_of_day = tokyo_end_of_day()
        overdue = datetime.now(UTC) - timedelta(hours=1)
        later_today = end_of_day - timedelta(seconds=1)
        tomorrow = end_of_day + timedelta(seconds=1)
        await set_memory_due(async_session_maker, "кот", "front", overdue)
        await set_memory_due(async_session_maker, "пёс", "front", later_today)
        await set_memory_due(async_session_maker, "лис", "front", tomorrow)
        await set_memory_due(async_session_maker, "кот", "back", overdue)
        for front_text in ("пёс", "лис"):
            await set_memory_due(
                async_session_maker,
                front_text,
                "back",
                end_of_day + timedelta(days=30),
            )

        response = await client.get("/bff/reviews/summary")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "timezone": "Asia/Tokyo",
            "sides": {
                "front": {"due_now": 1, "due_today": 2, "next_due_at": iso(later_today)},
                "back": {
                    "due_now": 1,
                    "due_today": 1,
                    "next_due_at": iso(end_of_day + timedelta(days=30)),
                },
            },
            "active_session": None,
        }

    async def test_counts_only_words_from_studiable_decks(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        bob = await user_factory(username="bob", email="bob@example.com")
        alice_client = await auth_client_factory(alice)
        bob_client = await auth_client_factory(bob)
        kept_uuid = await create_deck(alice_client, "Kept", [("кот", "cat")])
        deleted_uuid = await create_deck(alice_client, "Deleted", [("пёс", "dog")])
        public_uuid = await create_deck(
            bob_client,
            "Public",
            [("лис", "fox")],
            is_public=True,
        )
        await study_deck(alice_client, kept_uuid, "front", {"кот": "cat"})
        await study_deck(alice_client, deleted_uuid, "front", {"пёс": "dog"})
        await study_deck(alice_client, public_uuid, "front", {"лис": "fox"})
        overdue = datetime.now(UTC) - timedelta(hours=1)
        for front_text in ("кот", "пёс", "лис"):
            await set_memory_due(async_session_maker, front_text, "front", overdue)
        response = await alice_client.delete(f"/decks/{deleted_uuid}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        response = await bob_client.patch(
            f"/decks/{public_uuid}", json={"is_public": False}
        )
        assert response.status_code == status.HTTP_200_OK

        response = await alice_client.get("/bff/reviews/summary")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["sides"] == {
            "front": {"due_now": 1, "due_today": 1, "next_due_at": None},
            "back": EMPTY_SIDE,
        }

    async def test_shows_active_review_session(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await study_deck(client, deck_uuid, "front", {"кот": "cat"})
        await set_memory_due(
            async_session_maker,
            "кот",
            "front",
            datetime.now(UTC) - timedelta(hours=1),
        )
        review = await start_review(client, "front", 10)

        response = await client.get("/bff/reviews/summary")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["active_session"] == {
            "training_session_uuid": review["training_session_uuid"],
            "prompt_side": "front",
            "answered_count": 0,
            "total_count": 1,
        }

    async def test_ignores_deck_sessions_as_active_review(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await start_practice(client, deck_uuid, "front", 1)

        response = await client.get("/bff/reviews/summary")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["active_session"] is None

    async def test_rejects_unauthenticated_request(
        self,
        client_factory: ClientFactory,
    ):
        guest_client = await client_factory()

        response = await guest_client.get("/bff/reviews/summary")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {
            "code": "ACCESS_TOKEN_NOT_FOUND",
            "message": "Not authorized",
        }
