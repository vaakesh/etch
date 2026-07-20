from fastapi import APIRouter, Depends, Query

from app.auth.deps import get_current_user
from app.bff.home.schemas import DeckPageData, HomeDashboard
from app.users.models import User
from app.bff.home.deps import get_bff_service
from app.bff.home.service import BffService


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