from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.cards.deps import get_card_service
from app.cards.schemas import CardCreate, CardOut, CardSchema, CardUpdate
from app.cards.service import CardService
from app.auth.deps import get_current_user
from app.users.models import User


router = APIRouter(prefix="/cards")


@router.get("/", response_model=list[CardSchema])
async def get_all_cards_by_limit(
    limit: int = 10,
    card_service: CardService = Depends(get_card_service),
):
    return await card_service.get_all_cards_by_limit(limit)


@router.get("/{card_uuid}", response_model=CardSchema)
async def get_card(
    card_uuid: UUID,
    card_service: CardService = Depends(get_card_service),
):
    return await card_service.get_by_uuid(card_uuid)


@router.post("/", response_model=CardOut)
async def create_card(
    payload: CardCreate,
    card_service: CardService = Depends(get_card_service),
    current_user: User = Depends(get_current_user),
):
    return await card_service.create_card(payload, current_user.id)


@router.patch("/{card_uuid}", response_model=CardSchema)
async def update_card(
    card_uuid: UUID,
    payload: CardUpdate,
    card_service: CardService = Depends(get_card_service),
):
    return await card_service.update_card(
        card_uuid,
        payload,
    )


@router.delete("/{card_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_uuid: UUID,
    card_service: CardService = Depends(get_card_service),
):
    await card_service.delete_card(card_uuid)
    return None