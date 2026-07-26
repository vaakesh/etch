from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.auth.deps import get_current_user
from app.bff.schemas import CreateTrainingSession, DeckPageData, DeckPageFavouritesDecks, HomeDashboard, PracticeSessionResponse, ResponseCardsLibraryPage
from app.users.models import User
from app.bff.deps import get_bff_service
from app.bff.service import BffService


router = APIRouter(prefix="/bff")


@router.get("/home", response_model=HomeDashboard)
async def get_home_dashboard(
    current_user: User = Depends(get_current_user),
    bff_service: BffService = Depends(get_bff_service),
):
    result = await bff_service.get_home_dashboard(current_user.id)
    return result


@router.get("/decks", response_model=DeckPageData)
async def get_deck_page_data(
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    bff_service: BffService = Depends(get_bff_service),
):
    result = await bff_service.get_deck_page_data(current_user.id, cursor=cursor)
    return result

@router.get("/decks/favourite", response_model=DeckPageFavouritesDecks)
async def get_deck_page_favourite_decks(
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    bff_service: BffService = Depends(get_bff_service),
):
    result = await bff_service.get_favourite_decks_by_user_id(
        user_id = current_user.id,
        cursor=cursor,
    )
    return result

@router.get("/library/cards", response_model=ResponseCardsLibraryPage)
async def get_cards_library_page(
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    bff_service: BffService = Depends(get_bff_service),
) -> ResponseCardsLibraryPage:
    result = await bff_service.get_cards_library_page_by_user_id(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        cursor=cursor,
    )
    return result

@router.post(
    "/practice/{deck_uuid}/start",
    response_model=PracticeSessionResponse,
)
async def start_practice_session(
    deck_uuid: UUID,
    payload: CreateTrainingSession,
    current_user: User = Depends(get_current_user),
    bff_service: BffService = Depends(get_bff_service),
):
    return await bff_service.start_practice_session(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
        prompt_side=payload.prompt_side,
    )

@router.post(
    "/practice/{training_session_uuid}/continue",
    response_model=PracticeSessionResponse,
)
async def continue_practice_session(
    training_session_uuid: UUID,
    current_user: User = Depends(get_current_user),
    bff_service: BffService = Depends(get_bff_service),
):
    return await bff_service.continue_practice_session(
        user_id=current_user.id,
        training_session_uuid=training_session_uuid,
    )