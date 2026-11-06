import logging
from datetime import timedelta

import pytest
from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.card_memory.models import CardMemoryState
from app.card_memory.rebuild import RebuildStats, rebuild_card_memory
from app.cards.models import Card
from app.fsrs.types import CardState
from app.service import UnitOfWork
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
            select(CardMemoryState).order_by(CardMemoryState.learning_key)
        )
        return list(result)


async def load_items(
    async_session_maker: async_sessionmaker[AsyncSession],
) -> list[TrainingSessionItem]:
    async with async_session_maker() as session:
        result = await session.scalars(
            select(TrainingSessionItem).order_by(TrainingSessionItem.id)
        )
        return list(result)


async def delete_memory_states(
    async_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    # Состояние журнала до появления card_memory_states
    async with async_session_maker.begin() as session:
        await session.execute(delete(CardMemoryState))


async def rebuild(
    async_session_maker: async_sessionmaker[AsyncSession],
    *,
    apply: bool,
    batch_size: int = 500,
) -> RebuildStats:
    return await rebuild_card_memory(
        lambda: UnitOfWork(async_session_maker),
        apply=apply,
        batch_size=batch_size,
    )


class TestRebuildCardMemory:
    async def test_missing_state_restored_from_journal(
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
        await delete_memory_states(async_session_maker)

        stats = await rebuild(async_session_maker, apply=True)

        assert stats == RebuildStats(batches=1, keys=1, events=2, created=1)
        async with async_session_maker() as session:
            user = (await session.scalars(select(User))).one()
            card = (await session.scalars(select(Card))).one()
        last_item = (await load_items(async_session_maker))[-1]
        assert last_item.answered_at is not None
        memory = (await load_memory_states(async_session_maker))[0]
        # GOOD -> GOOD в тот же день, как пошаговое обновление в submit_answer
        assert memory.user_id == user.id
        assert memory.learning_key == card.learning_key
        assert memory.prompt_side == "front"
        assert memory.state == CardState.REVIEW
        assert memory.step is None
        assert memory.stability == 2.3065
        assert memory.difficulty == pytest.approx(2.111214235785395, rel=1e-12)
        assert memory.last_review == last_item.answered_at
        assert memory.due == last_item.answered_at + timedelta(days=2)

    async def test_state_built_without_history_replaced(
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
        await delete_memory_states(async_session_maker)
        second = await start_practice(client, deck_uuid, "front", 1)
        response = await submit_answer(
            client, second["training_session_uuid"], 1, "cat",
        )
        assert response.status_code == status.HTTP_200_OK
        # submit_answer начал слово заново и не учёл первый ответ
        stale = (await load_memory_states(async_session_maker))[0]
        assert stale.state == CardState.LEARNING
        assert stale.step == 1

        stats = await rebuild(async_session_maker, apply=True)

        assert stats == RebuildStats(batches=1, keys=1, events=2, updated=1)
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.state == CardState.REVIEW
        assert memory.step is None
        assert memory.stability == 2.3065
        assert memory.difficulty == pytest.approx(2.111214235785395, rel=1e-12)
        assert memory.last_review == stale.last_review
        assert memory.due == stale.last_review + timedelta(days=2)

    async def test_self_rating_replayed_instead_of_automatic(
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
        response = await rate_answer(client, practice["training_session_uuid"], 1, 4)
        assert response.status_code == status.HTTP_200_OK
        await delete_memory_states(async_session_maker)

        stats = await rebuild(async_session_maker, apply=True)

        assert stats == RebuildStats(batches=1, keys=1, events=1, created=1)
        item = (await load_items(async_session_maker))[0]
        assert item.answered_at is not None
        memory = (await load_memory_states(async_session_maker))[0]
        assert memory.state == CardState.REVIEW
        assert memory.step is None
        assert memory.stability == 8.2956
        assert memory.difficulty == 1.0
        assert memory.last_review == item.answered_at
        assert memory.due == item.answered_at + timedelta(days=8)

    async def test_states_in_sync_left_unchanged(
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
        before = (await load_memory_states(async_session_maker))[0]

        stats = await rebuild(async_session_maker, apply=True)

        assert stats == RebuildStats(batches=1, keys=1, events=1, unchanged=1)
        after = (await load_memory_states(async_session_maker))[0]
        assert after.to_fsrs_card() == before.to_fsrs_card()

    async def test_dry_run_reports_without_changes(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(
            client, [("кот", "cat"), ("пёс", "dog")],
        )
        first = await start_practice(client, deck_uuid, "front", 1)
        await submit_answer(client, first["training_session_uuid"], 1, "cat")
        await delete_memory_states(async_session_maker)
        # Слово из первой сессии получает состояние без своей истории,
        # другое слово отвечают впервые, и его состояние верное
        second = await start_practice(client, deck_uuid, "front", 2)
        await submit_answer(client, second["training_session_uuid"], 1, None)
        await submit_answer(client, second["training_session_uuid"], 2, None)
        before = [
            state.to_fsrs_card()
            for state in await load_memory_states(async_session_maker)
        ]

        stats = await rebuild(async_session_maker, apply=False)

        assert stats == RebuildStats(
            batches=1, keys=2, events=3, created=0, updated=1, unchanged=1,
        )
        after = [
            state.to_fsrs_card()
            for state in await load_memory_states(async_session_maker)
        ]
        assert after == before

    async def test_all_keys_processed_across_batches(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        alice = await user_factory(username="alice", email="alice@example.com")
        client = await auth_client_factory(alice)
        deck_uuid = await create_deck_with_cards(
            client, [("кот", "cat"), ("пёс", "dog")],
        )
        practice = await start_practice(client, deck_uuid, "front", 2)
        await submit_answer(client, practice["training_session_uuid"], 1, None)
        await submit_answer(client, practice["training_session_uuid"], 2, None)
        await delete_memory_states(async_session_maker)

        stats = await rebuild(async_session_maker, apply=True, batch_size=1)

        assert stats == RebuildStats(batches=2, keys=2, events=2, created=2)
        async with async_session_maker() as session:
            learning_keys = sorted(
                (await session.scalars(select(Card.learning_key))).all()
            )
        states = await load_memory_states(async_session_maker)
        assert [state.learning_key for state in states] == learning_keys
        for state in states:
            assert state.state == CardState.LEARNING
            assert state.step == 0
            assert state.stability == 0.212
            assert state.difficulty == 6.4133
