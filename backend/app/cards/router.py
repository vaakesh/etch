from uuid import UUID

from app.auth.deps import CurrentUser, get_current_user
from app.cards.deps import CardServiceDeps, get_card_service
from app.cards.schemas import CardCreate, CardDetail, CardUpdate
from app.cards.service import CardService
from app.users.models import User
from fastapi import APIRouter, Depends, Response, status

router = APIRouter(prefix="/cards")


@router.get("/{card_uuid}", response_model=CardDetail)
async def get_card(
    card_uuid: UUID,
    card_service: CardServiceDeps,
):
    return await card_service.get_by_uuid(
        card_uuid,
    )


@router.post("/", response_model=CardDetail)
async def create_card(
    payload: CardCreate,
    card_service: CardService = Depends(get_card_service),
    current_user: User = Depends(get_current_user),
):
    return await card_service.create_card(payload, current_user.id)


@router.patch("/{card_uuid}", response_model=CardDetail)
async def update_card(
    card_uuid: UUID,
    payload: CardUpdate,
    current_user: CurrentUser,
    card_service: CardServiceDeps,
):
    return await card_service.update_card(
        card_uuid,
        current_user.id,
        payload,
    )


@router.delete("/{card_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_uuid: UUID,
    current_user: CurrentUser,
    card_service: CardService = Depends(get_card_service),
):
    await card_service.delete_card(
        user_id=current_user.id,
        card_uuid=card_uuid,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    return response