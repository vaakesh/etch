from uuid import UUID

from app.auth.deps import CurrentUser, get_current_user
from app.bff.deps import get_bff_service
from app.bff.schemas import (
    CatalogDeckItemResponse,
    HomeDashboardResponse,
    LibraryCardItemResponse,
    LibraryDeckItemResponse,
)
from app.bff.service import BffService
from app.common.schemas import CursorPage
from app.common.types import PageLimit, PaginationCursor, SearchQuery
from app.training_sessions.schemas import (
    PracticeSessionResponse,
    StartPracticeSessionRequest,
)
from app.users.models import User
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/bff")


@router.get("/home", response_model=HomeDashboardResponse)
async def get_home_dashboard(
    current_user: CurrentUser,
    bff_service: BffService = Depends(get_bff_service),
):
    result = await bff_service.get_home_dashboard(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
    )
    return result

@router.get("/catalog", response_model=list[CatalogDeckItemResponse])
async def get_catalog_page(
    current_user: CurrentUser,
    search_query: SearchQuery = None,
    page: int = Query(default=1, ge=1),
    limit: PageLimit = 50,
    bff_service: BffService = Depends(get_bff_service),
):
    return await bff_service.get_catalog_page(
        user_id=current_user.id,
        search_query=search_query,
        page=page,
        limit=limit,
    )


@router.get("/library/decks", response_model=CursorPage[LibraryDeckItemResponse])
async def get_decks_library_page(
    current_user: CurrentUser,
    search_query: SearchQuery = None,
    cursor: PaginationCursor = None,
    is_favourite: bool | None = Query(default=False),
    limit: PageLimit = 50,
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


@router.get("/library/cards", response_model=CursorPage[LibraryCardItemResponse])
async def get_cards_library_page(
    current_user: CurrentUser,
    search_query: SearchQuery = None,
    cursor: PaginationCursor = None,
    limit: PageLimit = 50,
    bff_service: BffService = Depends(get_bff_service),
) -> CursorPage[LibraryCardItemResponse]:
    result = await bff_service.get_cards_library_page(
        user_id=current_user.id,
        user_uuid=current_user.uuid,
        search_query=search_query,
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
    payload: StartPracticeSessionRequest,
    current_user: User = Depends(get_current_user),
    bff_service: BffService = Depends(get_bff_service),
):
    return await bff_service.start_practice_session(
        user_id=current_user.id,
        deck_uuid=deck_uuid,
        prompt_side=payload.prompt_side,
        words_per_session=payload.words_per_session,
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
