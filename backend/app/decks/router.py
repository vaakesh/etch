from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.auth.deps import CurrentUser, OptionalCurrentUser
from app.cards.schemas import CardResponse, CreateCardRequest, LoadCardsRequest, LoadCardsResponse
from fastapi import APIRouter, Query, Response, status

from app.cards.deps import CardServiceDeps

from .deps import DeckServiceDeps, UserDeckServiceDeps
from .schemas import (
    CreateDeckRequest,
    DeckCardResponse,
    DeckResponse,
    UpdateDeckRequest,
    ReorderCards,
)

router = APIRouter(prefix="/decks")


@router.get("/{deck_uuid}", response_model=DeckResponse)
async def get_deck(
    deck_uuid: UUID,
    current_user: OptionalCurrentUser,
    deck_service: DeckServiceDeps,
):
    return await deck_service.get_by_uuid(
        deck_uuid=deck_uuid,
        current_user_id=current_user.id if current_user else None,
    )

@router.post("/create", response_model=DeckResponse)
async def create_deck(
    payload: CreateDeckRequest,
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
):
    return await deck_service.create_deck(
        payload, 
        user_id=current_user.id,
        user_uuid=current_user.uuid,
    )

@router.patch("/{deck_uuid}", response_model=DeckResponse)
async def update_deck(
    deck_uuid: UUID,
    payload: UpdateDeckRequest,
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
):
    return await deck_service.update_deck(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        deck_uuid=deck_uuid,
        payload=payload,
    )

@router.delete("/{deck_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck(
    deck_uuid: UUID,
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
):
    await deck_service.delete_deck(
        deck_uuid=deck_uuid,
        user_id=current_user.id,
        user_uuid=current_user.uuid,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    return response

@router.get("/{deck_uuid}/cards", response_model=list[CardResponse])
async def get_deck_cards(
    deck_uuid: UUID,
    current_user: OptionalCurrentUser,
    deck_service: DeckServiceDeps,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=50),
):
    return await deck_service.get_deck_cards(
        user_id=current_user.id if current_user else None,
        deck_uuid=deck_uuid,
        offset=offset,
        limit=limit,
    )

@router.get(
    "/{deck_uuid}/cards/{card_uuid}",
    response_model=CardResponse,
)
async def get_card_in_deck(
    deck_uuid: UUID,
    card_uuid: UUID,
    current_user: OptionalCurrentUser,
    card_service: CardServiceDeps,
):
    return await card_service.get_card_in_deck(
        card_uuid=card_uuid,
        deck_uuid=deck_uuid,
        viewer_id=current_user.id if current_user else None,
    )

@router.post(
    "/{deck_uuid}/cards/remove/{card_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_card_from_deck(
    deck_uuid: UUID,
    card_uuid: UUID,
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
):
    await deck_service.remove_card_from_deck(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        deck_uuid=deck_uuid,
        card_uuid=card_uuid,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    return response

# todo: complete the logic of cards reordering
@router.post(
    "/{deck_uuid}/cards/reorder",
)
async def reorder_deck_cards(
    deck_uuid: UUID,
    payload: ReorderCards,
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
):
    await deck_service.reorder_cards(
            user_id=current_user.id,
            deck_uuid=deck_uuid,
            card_uuid=payload.card_uuid,
            to_position=payload.to_position,
    )

@router.post(
    "/{deck_uuid}/cards/import",
    response_model=LoadCardsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def load_cards_to_deck(
    deck_uuid: UUID,
    payload: LoadCardsRequest,
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
):
    return await deck_service.load_cards_to_deck(
        deck_uuid=deck_uuid,
        cards=payload.cards,
        user_id=current_user.id,
        user_uuid=current_user.uuid,
    )

@router.post(
    "/{deck_uuid}/cards/{card_uuid}",
    response_model=DeckCardResponse,
)
async def add_card_to_deck(
    deck_uuid: UUID,
    card_uuid: UUID,
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
):
    new_deck_card = await deck_service.add_card_to_deck(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        deck_uuid=deck_uuid,
        card_uuid=card_uuid,
    )
    return new_deck_card


@router.patch(
    "/{deck_uuid}/set-favourite",
)
async def set_favourite(
    deck_uuid: UUID,
    current_user: CurrentUser,
    user_deck_service: UserDeckServiceDeps,
    value: bool = True,
):
    user_deck = await user_deck_service.set_favourite_deck(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        deck_uuid=deck_uuid,
        value=value,
    )
    return user_deck.is_favourite


@router.post(
    "/{deck_uuid}/save",
    status_code=status.HTTP_200_OK,
)
async def save_deck(
    deck_uuid: UUID,
    current_user: CurrentUser,
    user_deck_service: UserDeckServiceDeps,
):
    await user_deck_service.save_deck(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        deck_uuid=deck_uuid,
    )
    response = Response(status_code=status.HTTP_200_OK)
    return response

@router.post(
    "/{deck_uuid}/unsave",
    status_code=status.HTTP_200_OK,
)
async def unsave_deck(
    deck_uuid: UUID,
    current_user: CurrentUser,
    user_deck_service: UserDeckServiceDeps,
):
    await user_deck_service.unsave_deck(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        deck_uuid=deck_uuid,
    )
    response = Response(status_code=status.HTTP_200_OK)
    return response
