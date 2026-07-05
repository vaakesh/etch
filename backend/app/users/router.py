from fastapi import APIRouter, Depends, Query, Request, Response, status

from uuid import UUID

from app.users.service import UserService
from app.users.deps import get_user_service
from app.users.schemas import UserCreate, UserOut, UserSchema, UserUpdate
from app.training_sessions.schemas import TrainingSessionSchema
from backend.app.cards.deps import get_card_service
from backend.app.cards.schemas import CardSchema
from backend.app.cards.service import CardService
from backend.app.decks.deps import get_deck_service
from backend.app.decks.schemas import DeckSchema
from backend.app.decks.service import DeckService
from backend.app.training_sessions.deps import get_training_session_service
from backend.app.training_sessions.service import TrainingSessionService


router = APIRouter(prefix="/users")

@router.get("/", response_model=list[UserSchema])
async def get_all_users_by_limit(
    limit: int = 10,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.get_all_users_by_limit(limit)

@router.get("/{user_uuid}", response_model=UserSchema)
async def get_public_user(
    user_uuid: UUID,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.get_by_uuid(user_uuid)

@router.post("/", response_model=UserOut)
async def create_user(
    payload: UserCreate,
    user_service: UserService = Depends(get_user_service),
):
    user = await user_service.create_user(payload)
    return user

@router.patch("/{user_uuid}", response_model=UserSchema)
async def update_user(
    user_uuid: UUID,
    payload: UserUpdate,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.update_user(user_uuid, payload)

@router.delete("/{user_uuid}", response_model=UserSchema)
async def delete_user(
    user_uuid: UUID,
    user_service: UserService = Depends(get_user_service),
):
    return await user_service.delete_user(user_uuid)


# ----


@router.get("/{user_uuid}/training-sessions", response_model=list[TrainingSessionSchema])
async def get_training_sessions_by_user(
    user_uuid: UUID,
    limit: int = Query(default=10, ge=1, le=100),
    training_session_service: TrainingSessionService = Depends(get_training_session_service),
):
    return await training_session_service.get_all_by_user_uuid(
        user_uuid=user_uuid,
        limit=limit,
    )


@router.get("/{user_uuid}/decks", response_model=list[DeckSchema])
async def get_decks_by_user(
    user_uuid: UUID,
    limit: int = 10,
    deck_service: DeckService = Depends(get_deck_service),
):
    return await deck_service.get_all_by_user_uuid(
        user_uuid=user_uuid,
        limit=limit,
    )

@router.get("/{user_uuid}/cards", response_model=list[CardSchema])
async def get_cards_by_user_id(
    user_uuid: UUID,
    limit: int = 10,
    card_service: CardService = Depends(get_card_service),
):
    return await card_service.get_all_by_user_uuid(
        user_uuid=user_uuid,
        limit=limit,
    )