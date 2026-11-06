from datetime import datetime, timedelta
from typing import Any

from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.card_memory.models import CardMemoryState
from app.cards.models import Card
from tests.integration.training_sessions.conftest import start_practice, submit_answer
from tests.integration.users.conftest import (  # noqa: F401 # shared user fixtures
    auth_client_factory,
    user_factory,
    user_payload_factory,
)


async def create_deck(
    client: AsyncClient,
    title: str,
    cards: list[tuple[str, str]],
    is_public: bool = False,
) -> str:
    response = await client.post(
        "/decks/create",
        json={"title": title, "is_public": is_public},
    )
    assert response.status_code == status.HTTP_200_OK
    deck_uuid = response.json()["uuid"]

    response = await client.post(
        f"/decks/{deck_uuid}/cards/import",
        json={
            "cards": [
                {"front_text": front, "back_text": back, "front_lang": "ru", "back_lang": "en"}
                for front, back in cards
            ],
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    return deck_uuid


async def study_deck(
    client: AsyncClient,
    deck_uuid: str,
    prompt_side: str,
    answers: dict[str, str],
) -> None:
    # Правильный ответ на каждое слово колоды создаёт память FSRS
    practice = await start_practice(client, deck_uuid, prompt_side, len(answers))
    for card in practice["cards"]:
        response = await submit_answer(
            client,
            practice["training_session_uuid"],
            card["sequence_number"],
            answers[card["prompt_text"]],
        )
        assert response.status_code == status.HTTP_200_OK


async def set_memory_due(
    async_session_maker: async_sessionmaker[AsyncSession],
    front_text: str,
    prompt_side: str,
    due: datetime,
) -> None:
    # Срок задаётся явно, чтобы тест не зависел от расписания FSRS.
    # last_review сдвигается вместе с ним: due >= last_review
    async with async_session_maker() as session:
        learning_key = (
            await session.scalars(
                select(Card.learning_key).where(Card.front_text == front_text)
            )
        ).one()
        await session.execute(
            update(CardMemoryState)
            .where(
                CardMemoryState.learning_key == learning_key,
                CardMemoryState.prompt_side == prompt_side,
            )
            .values(due=due, last_review=due - timedelta(days=1))
        )
        await session.commit()


async def start_review(
    client: AsyncClient,
    prompt_side: str,
    words_per_session: int,
) -> dict[str, Any]:
    response = await client.post(
        "/bff/reviews/start",
        json={"prompt_side": prompt_side, "words_per_session": words_per_session},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()
