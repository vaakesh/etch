from typing import Any

from fastapi import status
from httpx import AsyncClient, Response

from tests.integration.users.conftest import (  # noqa: F401 # shared user fixtures
    auth_client_factory,
    user_factory,
    user_payload_factory,
)


async def create_deck_with_cards(
    client: AsyncClient,
    cards: list[tuple[str, str]],
) -> str:
    response = await client.post(
        "/decks/create",
        json={"title": "Animals", "is_public": False},
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


async def start_practice(
    client: AsyncClient,
    deck_uuid: str,
    prompt_side: str,
    words_per_session: int,
) -> dict[str, Any]:
    response = await client.post(
        f"/bff/practice/{deck_uuid}/start",
        json={"prompt_side": prompt_side, "words_per_session": words_per_session},
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()


async def submit_answer(
    client: AsyncClient,
    session_uuid: str,
    sequence_number: int,
    answer: str | None,
) -> Response:
    payload = (
        {"action": "skip"} if answer is None else {"action": "answer", "answer": answer}
    )
    return await client.put(
        f"/training-sessions/{session_uuid}/items/{sequence_number}/submit",
        json=payload,
    )


async def rate_answer(
    client: AsyncClient,
    session_uuid: str,
    sequence_number: int,
    rating: int,
) -> Response:
    return await client.put(
        f"/training-sessions/{session_uuid}/items/{sequence_number}/rating",
        json={"rating": rating},
    )
