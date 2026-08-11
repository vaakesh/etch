import asyncio
from uuid import UUID

from app.auth.deps import CurrentUser, get_current_user
from app.bff.deps import get_bff_service
from app.bff.schemas import (
    CardLibraryPage,
    CreateTrainingSession,
    DeckLibraryPage,
    HomeDashboard,
    PracticeSessionResponse,
)
from app.bff.service import BffService
from app.decks.schemas import CursorPage
from app.redis.deps import CacheServiceDeps
from app.users.models import User
from fastapi import APIRouter, Depends, Query

from app.users.schemas import SearchQuery

router = APIRouter(prefix="/bff")


@router.get("/home", response_model=HomeDashboard)
async def get_home_dashboard(
    current_user: CurrentUser,
    bff_service: BffService = Depends(get_bff_service),
):
    result = await bff_service.get_home_dashboard(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
    )
    return result


@router.get("/library/decks", response_model=CursorPage[DeckLibraryPage])
async def get_decks_library_page(
    current_user: CurrentUser,
    search_query: SearchQuery = None,
    cursor: str | None = Query(default=None),
    is_favourite: bool | None = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    bff_service: BffService = Depends(get_bff_service),
):
    result = await bff_service.get_decks_library_page(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        search_query=search_query,
        is_favourite=is_favourite,
        cursor=cursor,
        limit=limit,
    )
    return result


@router.get("/library/cards", response_model=CursorPage[CardLibraryPage])
async def get_cards_library_page(
    current_user: CurrentUser,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50),
    bff_service: BffService = Depends(get_bff_service),
) -> CursorPage[CardLibraryPage]:
    result = await bff_service.get_cards_library_page(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        cursor=cursor,
        limit=limit,
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

@router.get(
    "/practice/{training_session_uuid}/resume",
    response_model=PracticeSessionResponse,
)
async def resume_practice_session(
    training_session_uuid: UUID,
    current_user: User = Depends(get_current_user),
    bff_service: BffService = Depends(get_bff_service),
):
    return await bff_service.resume_practice_session(
        user_id=current_user.id,
        training_session_uuid=training_session_uuid,
    )