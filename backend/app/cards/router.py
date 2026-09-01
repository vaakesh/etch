from uuid import UUID

from app.auth.deps import CurrentUser, OptionalCurrentUser, get_current_user
from app.cards.deps import CardServiceDeps, get_card_service
from app.cards.schemas import CreateCardRequest, CardResponse, UpdateCardRequest
from app.cards.service import CardService
from app.redis.rate_limiters import cards_rate_limit
from app.users.models import User
from fastapi import APIRouter, Depends, Response, status

router = APIRouter(
    prefix="/cards",
    dependencies=[Depends(cards_rate_limit)],
)

@router.post("/", response_model=CardResponse)
async def create_card(
    payload: CreateCardRequest,
    card_service: CardService = Depends(get_card_service),
    current_user: User = Depends(get_current_user),
):
    return await card_service.create_card(
        payload=payload,
        user_id=current_user.id,
    )


@router.patch("/{card_uuid}", response_model=CardResponse)
async def update_card(
    card_uuid: UUID,
    payload: UpdateCardRequest,
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
