from uuid import UUID

from fastapi import APIRouter, Depends, status

from .deps import get_deck_service
from .schemas import (
    DeckCardAdd,
    DeckCardSchema,
    DeckCardUpdate,
    DeckCreate,
    DeckOut,
    DeckSchema,
    DeckUpdate,
)
from .service import DeckService


router = APIRouter(prefix="/decks")


@router.get("/", response_model=list[DeckSchema])
async def get_all_decks_by_limit(
    limit: int = 10,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_all_decks_by_limit(limit)


@router.get("/public", response_model=list[DeckSchema])
async def get_public_decks_by_limit(
    limit: int = 10,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_public_decks_by_limit(limit)


@router.get("/{deck_uuid}", response_model=DeckSchema)
async def get_deck(
    deck_uuid: UUID,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_by_uuid(deck_uuid)


@router.post("/", response_model=DeckOut)
async def create_deck(
    payload: DeckCreate,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.create_deck(payload)


@router.patch("/{deck_uuid}", response_model=DeckSchema)
async def update_deck(
    deck_uuid: UUID,
    payload: DeckUpdate,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.update_deck(
        deck_uuid,
        payload,
    )


@router.delete("/{deck_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(
    deck_uuid: UUID,
    deck_service: DeckService = Depends(get_deck_service),
):
    await deck_service.delete_deck(deck_uuid)
    return None


@router.get("/{deck_uuid}/cards", response_model=list[DeckCardSchema])
async def get_deck_cards(
    deck_uuid: UUID,
    limit: int = 100,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_deck_cards(
        deck_uuid=deck_uuid,
        limit=limit,
    )


@router.post(
    "/{deck_uuid}/cards/{card_uuid}",
    response_model=DeckCardSchema,
)
async def add_card_to_deck(
    deck_uuid: UUID,
    card_uuid: UUID,
    payload: DeckCardAdd,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.add_card_to_deck(
        deck_uuid=deck_uuid,
        card_uuid=card_uuid,
        payload=payload,
    )


@router.patch(
    "/{deck_uuid}/cards/{card_uuid}",
    response_model=DeckCardSchema,
)
async def update_deck_card(
    deck_card_uuid: UUID,
    payload: DeckCardUpdate,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.update_deck_card(
        deck_card_uuid=deck_card_uuid,
        position=payload.position,
    )


@router.delete(
    "/{deck_uuid}/cards/{card_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_card_from_deck(
    deck_uuid: UUID,
    card_uuid: UUID,
    deck_service: DeckService = Depends(get_deck_service),
):
    await deck_service.remove_card_from_deck(
        deck_uuid=deck_uuid,
        card_uuid=card_uuid,
    )
    return None