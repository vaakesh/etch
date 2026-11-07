import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.card_memory.models import CardMemoryState
from app.cards.models import Card
from app.training_sessions.models import (
    TrainingSession,
    TrainingSessionItem,
    TrainingSessionKind,
    TrainingSessionStatus,
)
from app.users.models import User
from tests.integration.reviews.conftest import (
    create_deck,
    set_memory_due,
    start_review,
    study_deck,
)
from tests.integration.training_sessions.conftest import submit_answer
from tests.integration.users.conftest import AuthClientFactory, UserFactory

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio(loop_scope="session")

ANSWERS = {"кот": "cat", "пёс": "dog", "лис": "fox"}


async def load_review_sessions(
    async_session_maker: async_sessionmaker[AsyncSession],
) -> list[TrainingSession]:
    async with async_session_maker() as session:
        result = await session.scalars(
            select(TrainingSession)
            .where(TrainingSession.kind == TrainingSessionKind.REVIEW)
            .order_by(TrainingSession.id)
        )
        return list(result)


class TestStartReviewSession:
    async def test_starts_session_with_most_overdue_words(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", list(ANSWERS.items()))
        await study_deck(client, deck_uuid, "front", ANSWERS)
        now = datetime.now(UTC)
        await set_memory_due(async_session_maker, "кот", "front", now - timedelta(days=3))
        await set_memory_due(async_session_maker, "пёс", "front", now - timedelta(days=2))
        await set_memory_due(async_session_maker, "лис", "front", now - timedelta(days=1))

        response = await client.post(
            "/bff/reviews/start",
            json={"prompt_side": "front", "words_per_session": 2},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        cards = sorted(data.pop("cards"), key=lambda card: card["prompt_text"])
        session_uuid = data.pop("training_session_uuid")
        started_at = data.pop("started_at")
        assert data == {
            "kind": "review",
            "deck_uuid": None,
            "prompt_side": "front",
            "answer_side": "back",
            "total_count": 2,
            "answered_count": 0,
            "correct_count": 0,
            "wrong_count": 0,
        }
        assert [card["prompt_text"] for card in cards] == ["кот", "пёс"]
        assert {card["sequence_number"] for card in cards} == {1, 2}
        assert all(
            (card["prompt_language"], card["answer_language"]) == ("ru", "en")
            for card in cards
        )
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            review = (
                await session.scalars(
                    select(TrainingSession).where(
                        TrainingSession.kind == TrainingSessionKind.REVIEW,
                    )
                )
            ).one()
            items = list(
                await session.scalars(
                    select(TrainingSessionItem)
                    .where(TrainingSessionItem.training_session_id == review.id)
                    .order_by(TrainingSessionItem.prompt_text)
                )
            )
            cards_by_text = {
                card.front_text: card for card in await session.scalars(select(Card))
            }
        assert str(review.uuid) == session_uuid
        assert review.started_at == datetime.fromisoformat(started_at)
        assert review.user_id == user.id
        assert review.deck_id is None
        assert review.deck_title_snapshot is None
        assert review.status == TrainingSessionStatus.IN_PROGRESS
        assert review.requested_count == 2
        assert [
            (
                item.prompt_text,
                item.answer_text,
                item.user_id,
                item.original_card_id,
                item.learning_key_snapshot,
                item.is_answered,
            )
            for item in items
        ] == [
            (
                "кот",
                "cat",
                user.id,
                cards_by_text["кот"].id,
                cards_by_text["кот"].learning_key,
                False,
            ),
            (
                "пёс",
                "dog",
                user.id,
                cards_by_text["пёс"].id,
                cards_by_text["пёс"].learning_key,
                False,
            ),
        ]

    async def test_takes_only_words_of_requested_side_due_today(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", list(ANSWERS.items()))
        await study_deck(client, deck_uuid, "front", ANSWERS)
        await study_deck(client, deck_uuid, "back", {v: k for k, v in ANSWERS.items()})
        now = datetime.now(UTC)
        await set_memory_due(async_session_maker, "кот", "back", now - timedelta(hours=1))
        await set_memory_due(async_session_maker, "пёс", "back", now + timedelta(days=30))
        await set_memory_due(async_session_maker, "лис", "back", now + timedelta(days=30))
        await set_memory_due(async_session_maker, "лис", "front", now - timedelta(hours=1))

        review = await start_review(client, "back", 10)

        assert review["prompt_side"] == "back"
        assert review["answer_side"] == "front"
        assert review["total_count"] == 1
        assert [card["prompt_text"] for card in review["cards"]] == ["cat"]
        assert review["cards"][0]["prompt_language"] == "en"

    async def test_answer_in_review_session_updates_memory(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await study_deck(client, deck_uuid, "front", {"кот": "cat"})
        overdue = datetime.now(UTC) - timedelta(hours=1)
        await set_memory_due(async_session_maker, "кот", "front", overdue)
        review = await start_review(client, "front", 10)

        response = await submit_answer(client, review["training_session_uuid"], 1, "cat")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        next_review_at = body.pop("next_review_at")
        assert body == {
            "is_correct": True,
            "answer_text": "cat",
            "answered_count": 1,
            "correct_count": 1,
            "total_count": 1,
            "is_finished": True,
            "time_to_complete": 0,
        }
        async with async_session_maker() as session:
            memory = (await session.scalars(select(CardMemoryState))).one()
            item = (
                await session.scalars(
                    select(TrainingSessionItem)
                    .join(
                        TrainingSession,
                        TrainingSession.id == TrainingSessionItem.training_session_id,
                    )
                    .where(TrainingSession.kind == TrainingSessionKind.REVIEW)
                )
            ).one()
        assert item.answered_at is not None
        assert memory.last_review == item.answered_at
        assert memory.due > item.answered_at
        assert datetime.fromisoformat(next_review_at) == memory.due
        sessions = await load_review_sessions(async_session_maker)
        assert [session.status for session in sessions] == [TrainingSessionStatus.COMPLETED]

    async def test_resumes_review_session(
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

        response = await client.get(
            f"/bff/practice/{review['training_session_uuid']}/resume"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == review

    async def test_new_start_abandons_previous_review_session(
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
        first = await start_review(client, "front", 10)

        second = await start_review(client, "front", 10)

        sessions = await load_review_sessions(async_session_maker)
        assert [
            (str(session.uuid), session.status, session.finished_at is None)
            for session in sessions
        ] == [
            (first["training_session_uuid"], TrainingSessionStatus.ABANDONED, False),
            (second["training_session_uuid"], TrainingSessionStatus.IN_PROGRESS, True),
        ]

    async def test_rejects_start_without_due_words(
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
            datetime.now(UTC) + timedelta(days=30),
        )

        response = await client.post(
            "/bff/reviews/start",
            json={"prompt_side": "front", "words_per_session": 10},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "code": "NO_CARDS_TO_REVIEW",
            "message": "No cards are due for review today",
        }
        assert await load_review_sessions(async_session_maker) == []

    async def test_does_not_take_words_of_other_user(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        bob = await user_factory(username="bob", email="bob@example.com")
        alice_client = await auth_client_factory(alice)
        bob_client = await auth_client_factory(bob)
        public_uuid = await create_deck(
            alice_client,
            "Public",
            [("кот", "cat")],
            is_public=True,
        )
        await study_deck(bob_client, public_uuid, "front", {"кот": "cat"})
        await set_memory_due(
            async_session_maker,
            "кот",
            "front",
            datetime.now(UTC) - timedelta(hours=1),
        )

        response = await alice_client.post(
            "/bff/reviews/start",
            json={"prompt_side": "front", "words_per_session": 10},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "NO_CARDS_TO_REVIEW"
        bob_review = await start_review(bob_client, "front", 10)
        assert [card["prompt_text"] for card in bob_review["cards"]] == ["кот"]
