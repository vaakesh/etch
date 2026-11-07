import logging
from datetime import timedelta
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.card_memory.models import CardMemoryState
from app.cards.models import Card
from app.common.utils import utcnow
from app.fsrs.types import CardState
from app.users.models import User
from tests.integration.reviews.conftest import create_deck, study_deck
from tests.integration.users.conftest import (
    AuthClientFactory,
    CreatedUser,
    UserFactory,
)

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio(loop_scope="session")


async def put_memory(
    async_session_maker: async_sessionmaker[AsyncSession],
    user: CreatedUser,
    front_text: str,
    prompt_side: str,
    stability: float,
    elapsed_days: float,
) -> None:
    # Память задаётся явно: R зависит только от stability и давности повторения
    last_review = utcnow() - timedelta(days=elapsed_days)
    values = {
        "state": CardState.REVIEW,
        "step": None,
        "stability": stability,
        "difficulty": 5.0,
        "due": last_review + timedelta(days=stability),
        "last_review": last_review,
    }
    async with async_session_maker.begin() as session:
        user_id = (
            await session.scalars(select(User.id).where(User.uuid == user.uuid))
        ).one()
        learning_key = (
            await session.scalars(
                select(Card.learning_key).where(Card.front_text == front_text)
            )
        ).one()
        await session.execute(
            pg_insert(CardMemoryState)
            .values(
                user_id=user_id,
                learning_key=learning_key,
                prompt_side=prompt_side,
                **values,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "learning_key", "prompt_side"],
                set_=values,
            )
        )


async def get_home_deck(client: AsyncClient, deck_uuid: str) -> dict[str, Any]:
    response = await client.get("/bff/home")
    assert response.status_code == status.HTTP_200_OK
    (deck,) = [deck for deck in response.json()["decks"] if deck["uuid"] == deck_uuid]
    return deck


class TestHomeDeckKnowledge:
    async def test_unstudied_deck_returns_zero_knowledge(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat"), ("пёс", "dog")])

        response = await client.get("/bff/home")

        assert response.status_code == status.HTTP_200_OK
        (deck,) = response.json()["decks"]
        assert deck["uuid"] == deck_uuid
        assert deck["updated_at"] is not None
        expected = {
            "uuid": deck_uuid,
            "owner_uuid": alice.uuid,
            "title": "Animals",
            "description": None,
            "words_count": 2,
            "user_accuracy": 0,
            "user_knowledge": 0,
            "updated_at": deck["updated_at"],
        }
        assert deck == expected

    async def test_just_answered_deck_returns_full_knowledge(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat"), ("пёс", "dog")])
        await study_deck(client, deck_uuid, "front", {"кот": "cat", "пёс": "dog"})

        deck = await get_home_deck(client, deck_uuid)

        assert deck["user_knowledge"] == 100

    @pytest.mark.parametrize(
        ("stability", "elapsed_days", "expected"),
        [
            pytest.param(10.0, 10.0, 90, id="elapsed_equals_stability"),
            pytest.param(10.0, 30.0, 81, id="forgotten_over_time"),
            pytest.param(2.0, 3.0, 87, id="low_stability"),
        ],
    )
    async def test_knowledge_follows_forgetting_curve(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        stability: float,
        elapsed_days: float,
        expected: int,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await put_memory(
            async_session_maker, alice, "кот", "front", stability, elapsed_days
        )

        deck = await get_home_deck(client, deck_uuid)

        assert deck["user_knowledge"] == expected

    async def test_unstudied_words_count_as_zero(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat"), ("пёс", "dog")])
        # R = 0.9 у одного слова из двух
        await put_memory(async_session_maker, alice, "кот", "front", 10.0, 10.0)

        deck = await get_home_deck(client, deck_uuid)

        assert deck["user_knowledge"] == 45

    async def test_best_prompt_side_counts_for_word(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await put_memory(async_session_maker, alice, "кот", "front", 10.0, 30.0)
        await put_memory(async_session_maker, alice, "кот", "back", 10.0, 10.0)

        deck = await get_home_deck(client, deck_uuid)

        assert deck["user_knowledge"] == 90

    async def test_other_user_memory_not_counted(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        bob = await user_factory(username="bob", email="bob@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await put_memory(async_session_maker, bob, "кот", "front", 10.0, 10.0)

        deck = await get_home_deck(client, deck_uuid)

        assert deck["user_knowledge"] == 0


class TestLibraryDeckKnowledge:
    async def test_viewer_state_returns_knowledge(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat"), ("пёс", "dog")])
        await put_memory(async_session_maker, alice, "кот", "front", 10.0, 10.0)

        response = await client.get("/bff/library/decks")

        assert response.status_code == status.HTTP_200_OK
        (item,) = response.json()["items"]
        assert item["deck"]["uuid"] == deck_uuid
        expected = {
            "sessions_count": 0,
            "correct_count": 0,
            "wrong_count": 0,
            "accuracy": 0,
            "knowledge": 45,
            "last_studied_at": None,
            "is_favourite": False,
            "is_saved": False,
        }
        assert item["viewer_state"] == expected
