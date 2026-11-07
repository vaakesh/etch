import logging
from datetime import datetime, timedelta

import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.card_memory.models import CardMemoryState
from app.cards.models import Card
from app.fsrs.types import CardState
from app.training_sessions.models import TrainingSessionItem
from app.users.models import User
from tests.integration.training_sessions.conftest import (
    create_deck_with_cards,
    rate_answer,
    start_practice,
    submit_answer,
)
from tests.integration.users.conftest import AuthClientFactory, UserFactory

logger = logging.getLogger(__name__)
pytestmark = pytest.mark.asyncio(loop_scope="session")


async def load_memory_states(
    async_session_maker: async_sessionmaker[AsyncSession],
) -> list[CardMemoryState]:
    async with async_session_maker() as session:
        result = await session.scalars(
            select(CardMemoryState).order_by(CardMemoryState.prompt_side)
        )
        return list(result)


class TestSubmitAnswerCardMemory:
    async def test_correct_answer_stores_good_review(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        practice = await start_practice(client, deck_uuid, "front", 1)

        response = await submit_answer(
            client,
            practice["training_session_uuid"],
            1,
            "cat",
        )

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
            user = (await session.scalars(select(User))).one()
            card = (await session.scalars(select(Card))).one()
            item = (await session.scalars(select(TrainingSessionItem))).one()
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.user_id == user.id
        assert memory.learning_key == card.learning_key
        assert memory.prompt_side == "front"
        assert memory.state == CardState.LEARNING
        assert memory.step == 1
        assert memory.stability == 2.3065
        assert memory.difficulty == pytest.approx(2.118103970459016, rel=1e-12)
        assert item.answered_at is not None
        assert memory.last_review == item.answered_at
        assert memory.due == item.answered_at + timedelta(minutes=10)
        assert datetime.fromisoformat(next_review_at) == memory.due

    @pytest.mark.parametrize(
        "answer",
        [pytest.param("dog", id="wrong_answer"), pytest.param(None, id="skip")],
    )
    async def test_wrong_answer_or_skip_stores_again_review(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
        answer: str | None,
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        practice = await start_practice(client, deck_uuid, "front", 1)

        response = await submit_answer(
            client,
            practice["training_session_uuid"],
            1,
            answer,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_correct"] is False
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.state == CardState.LEARNING
        assert memory.step == 0
        assert memory.stability == 0.212
        assert memory.difficulty == 6.4133
        assert memory.last_review is not None
        assert memory.due == memory.last_review + timedelta(minutes=1)
        # «Не знаю» тоже сообщает, когда слово вернётся на повторение
        assert datetime.fromisoformat(response.json()["next_review_at"]) == memory.due

    async def test_next_session_updates_same_memory_row(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        first = await start_practice(client, deck_uuid, "front", 1)
        await submit_answer(client, first["training_session_uuid"], 1, "cat")
        second = await start_practice(client, deck_uuid, "front", 1)

        response = await submit_answer(
            client,
            second["training_session_uuid"],
            1,
            "cat",
        )

        assert response.status_code == status.HTTP_200_OK
        states = await load_memory_states(async_session_maker)
        assert len(states) == 1
        assert states[0].state == CardState.REVIEW
        assert states[0].step is None
        assert states[0].stability == 2.3065
        assert states[0].last_review is not None
        assert states[0].due == states[0].last_review + timedelta(days=2)

    async def test_keeps_separate_memory_per_prompt_side(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        forward = await start_practice(client, deck_uuid, "front", 1)
        await submit_answer(client, forward["training_session_uuid"], 1, "cat")
        backward = await start_practice(client, deck_uuid, "back", 1)

        response = await submit_answer(
            client,
            backward["training_session_uuid"],
            1,
            "dog",
        )

        assert response.status_code == status.HTTP_200_OK
        back, front = await load_memory_states(async_session_maker)
        assert (back.prompt_side, back.stability) == ("back", 0.212)
        assert (front.prompt_side, front.stability) == ("front", 2.3065)
        assert back.learning_key == front.learning_key

    async def test_repeated_submit_does_not_review_memory_twice(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        # Два слова: после первого ответа сессия ещё не завершена
        deck_uuid = await create_deck_with_cards(
            client,
            [("кот", "cat"), ("собака", "dog")],
        )
        practice = await start_practice(client, deck_uuid, "front", 2)
        await submit_answer(client, practice["training_session_uuid"], 1, "wrong")
        before = await load_memory_states(async_session_maker)

        response = await submit_answer(
            client,
            practice["training_session_uuid"],
            1,
            "wrong",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["answered_count"] == 1
        after = await load_memory_states(async_session_maker)
        assert [m.to_fsrs_card() for m in after] == [m.to_fsrs_card() for m in before]


async def load_items(
    async_session_maker: async_sessionmaker[AsyncSession],
) -> list[TrainingSessionItem]:
    async with async_session_maker() as session:
        result = await session.scalars(
            select(TrainingSessionItem).order_by(TrainingSessionItem.id)
        )
        return list(result)


class TestRateAnswer:
    async def test_easy_rating_replaces_automatic_good(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        practice = await start_practice(client, deck_uuid, "front", 1)
        await submit_answer(client, practice["training_session_uuid"], 1, "cat")

        response = await rate_answer(client, practice["training_session_uuid"], 1, 4)

        item = (await load_items(async_session_maker))[0]
        assert item.answered_at is not None
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "rating": 4,
            "next_review_at": (item.answered_at + timedelta(days=8))
            .isoformat()
            .replace("+00:00", "Z"),
        }
        assert item.self_rating == 4
        assert item.is_correct is True
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.state == CardState.REVIEW
        assert memory.step is None
        assert memory.stability == 8.2956
        assert memory.difficulty == 1.0
        assert memory.due == item.answered_at + timedelta(days=8)

    async def test_good_rating_after_typo_replaces_automatic_again(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        practice = await start_practice(client, deck_uuid, "front", 1)
        await submit_answer(client, practice["training_session_uuid"], 1, "cta")

        response = await rate_answer(client, practice["training_session_uuid"], 1, 3)

        assert response.status_code == status.HTTP_200_OK
        item = (await load_items(async_session_maker))[0]
        assert item.is_correct is False
        assert item.self_rating == 3
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.state == CardState.LEARNING
        assert memory.step == 1
        assert memory.stability == 2.3065

    async def test_rating_earlier_answer_replays_later_answers(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        first = await start_practice(client, deck_uuid, "front", 1)
        await submit_answer(client, first["training_session_uuid"], 1, "cat")
        second = await start_practice(client, deck_uuid, "front", 1)
        await submit_answer(client, second["training_session_uuid"], 1, "cat")

        response = await rate_answer(client, first["training_session_uuid"], 1, 1)

        # История стала AGAIN -> GOOD в тот же день, а не GOOD -> GOOD
        assert response.status_code == status.HTTP_200_OK
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.state == CardState.LEARNING
        assert memory.step == 1
        assert memory.stability == pytest.approx(0.24668918777567272, rel=1e-12)
        assert memory.difficulty == pytest.approx(6.402115069296838, rel=1e-12)

    async def test_changing_rating_overwrites_previous_one(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        practice = await start_practice(client, deck_uuid, "front", 1)
        await submit_answer(client, practice["training_session_uuid"], 1, "cat")
        await rate_answer(client, practice["training_session_uuid"], 1, 4)

        response = await rate_answer(client, practice["training_session_uuid"], 1, 2)

        assert response.status_code == status.HTTP_200_OK
        item = (await load_items(async_session_maker))[0]
        assert item.self_rating == 2
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.state == CardState.LEARNING
        assert memory.step == 0
        assert memory.stability == 1.2931

    async def test_rejects_unanswered_item_without_changes(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(client, [("кот", "cat")])
        practice = await start_practice(client, deck_uuid, "front", 1)

        response = await rate_answer(client, practice["training_session_uuid"], 1, 3)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            "code": "CARD_NOT_ANSWERED",
            "message": "Card must be answered before rating",
        }
        assert (await load_items(async_session_maker))[0].self_rating is None
        assert await load_memory_states(async_session_maker) == []

    async def test_hides_session_of_other_user(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        bob = await user_factory(username="bob", email="bob@example.com")
        alice_client = await auth_client_factory(alice)
        bob_client = await auth_client_factory(bob)
        deck_uuid = await create_deck_with_cards(alice_client, [("кот", "cat")])
        practice = await start_practice(alice_client, deck_uuid, "front", 1)
        await submit_answer(alice_client, practice["training_session_uuid"], 1, "cat")

        response = await rate_answer(bob_client, practice["training_session_uuid"], 1, 1)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["code"] == "TRAINING_SESSION_NOT_FOUND"
        assert (await load_items(async_session_maker))[0].self_rating is None
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.stability == 2.3065
