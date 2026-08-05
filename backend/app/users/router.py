from typing import Annotated
from uuid import UUID

from app.auth.cookies import clear_tokens_cookie
from app.auth.deps import AuthServiceDeps, CurrentUser
from app.cards.deps import CardServiceDeps
from app.cards.schemas import CardDetail
from app.decks.deps import DeckServiceDeps, UserDeckServiceDeps
from app.decks.schemas import CursorPage, DeckDetail, DeckWithUserState
from app.training_sessions.deps import (
    TrainingSessionServiceDeps,
)
from app.training_sessions.schemas import (
    TrainingSessionOut,
)
from app.users.deps import UserServiceDeps
from app.users.schemas import (
    ChangePassword,
    PrivateUserOut,
    PublicUserOut,
    SearchQuery,
    UserCreate,
    UserSettingsOut,
    UserSettingsUpdate,
    UserUpdate,
)
from fastapi import APIRouter, Query, Response, status

from app.training_sessions.models import TrainingSessionStatus

router = APIRouter(prefix="/users")

@router.get("/me", response_model=PrivateUserOut)
async def get_me(
    current_user: CurrentUser,
    user_service: UserServiceDeps,
):
    user_settings = await user_service.get_user_settings_by_id(
        user_id=current_user.id,
        for_update=False,
    )
    return PrivateUserOut(
        uuid=current_user.uuid,
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        user_settings=UserSettingsOut(
            locale=user_settings.locale,
            theme=user_settings.theme,
        )
    )

@router.patch("/me/settings", response_model=UserSettingsOut)
async def change_settings(
    current_user: CurrentUser,
    user_service: UserServiceDeps,
    payload: UserSettingsUpdate,
):
    new_user_settings = await user_service.update_user_settings(
        current_user_id=current_user.id,
        payload=payload,
    )
    return new_user_settings
    

@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePassword,
    current_user: CurrentUser,
    auth_service: AuthServiceDeps,
):
    await auth_service.change_password(
        user_id=current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_tokens_cookie(response=response)
    return response

@router.get("/me/decks", response_model=CursorPage[DeckDetail])
async def get_my_decks(
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    search_query: SearchQuery = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
):
    decks, next_cursor, has_more = await deck_service.get_all_by_user_uuid(
        user_uuid=current_user.uuid,
        search_query=search_query,
        cursor=cursor,
        limit=limit,
        public_only=False,
        current_user_id=current_user.id,
    )

    return CursorPage[DeckDetail](
        items=decks,
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get("/me/cards", response_model=CursorPage[CardDetail])
async def get_my_cards(
    current_user: CurrentUser,
    card_service: CardServiceDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
):
    cards, next_cursor, has_more = await card_service.get_all_by_user_id(
        user_id=current_user.id,
        cursor=cursor,
        limit=limit,
    )

    return CursorPage[CardDetail](
        items=cards,
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get("/me/training-sessions", response_model=CursorPage[TrainingSessionOut])
async def get_my_training_sessions(
    current_user: CurrentUser,
    training_session_service: TrainingSessionServiceDeps,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status: TrainingSessionStatus | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
):
    training_sessions, next_cursor, has_more = (
        await training_session_service.get_all_by_user_uuid(
            user_uuid=current_user.uuid,
            status=status,
            cursor=cursor,
            limit=limit,
        )
    )
    return CursorPage[TrainingSessionOut](
        items=training_sessions,
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get("/me/decks/followed", response_model=list[DeckWithUserState])
async def get_my_followed_decks(
    current_user: CurrentUser,
    user_deck_service: UserDeckServiceDeps,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[DeckWithUserState]:
    followed_decks = await user_deck_service.get_page_of_followed_decks_by_user_id(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )

    return followed_decks

@router.get("/{user_uuid}", response_model=PublicUserOut)
async def get_public_user(
    user_uuid: UUID,
    user_service: UserServiceDeps,
):
    user = await user_service.get_by_uuid(
        user_uuid=user_uuid,
        for_update=False,
    )
    return user

@router.post(
    "/create", 
    response_model=PrivateUserOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: UserCreate,
    user_service: UserServiceDeps,
):
    new_user, user_settings = await user_service.create_user(payload)
    return PrivateUserOut(
        uuid=new_user.uuid,
        username=new_user.username,
        email=new_user.email,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        user_settings=UserSettingsOut(
            locale=user_settings.locale,
            theme=user_settings.theme,
        )
    )

@router.patch("/me", response_model=PrivateUserOut)
async def update_user(
    payload: UserUpdate,
    current_user: CurrentUser,
    user_service: UserServiceDeps,
):
    updated_user = await user_service.update_user(
        target_user_uuid=current_user.uuid,
        current_user_id=current_user.id,
        payload=payload,
    )
    return updated_user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    current_user: CurrentUser,
    user_service: UserServiceDeps,
):
    await user_service.delete_user(
        current_user_id=current_user.id,
        target_user_uuid=current_user.uuid,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_tokens_cookie(response=response)
    return response

@router.get(
    "/{user_uuid}/training-sessions", 
    response_model=CursorPage[TrainingSessionOut]
)
async def get_public_training_sessions_by_user(
    user_uuid: UUID,
    training_session_service: TrainingSessionServiceDeps,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    training_sessions, next_cursor, has_more = (
        await training_session_service.get_all_by_user_uuid(
            user_uuid=user_uuid,
            status=TrainingSessionStatus.FINISHED,
            cursor=cursor,
            limit=limit,
        )
    )
    return CursorPage[TrainingSessionOut](
        items=training_sessions,
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get("/{user_uuid}/decks", response_model=CursorPage[DeckDetail])
async def get_public_decks_by_user(
    user_uuid: UUID,
    deck_service: DeckServiceDeps,
    search_query: SearchQuery = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
):
    decks, next_cursor, has_more = await deck_service.get_all_by_user_uuid(
        user_uuid=user_uuid,
        search_query=search_query,
        cursor=cursor,
        limit=limit,
        public_only=True,
        current_user_id=None,
    )

    return CursorPage[DeckDetail](
        items=decks,
        next_cursor=next_cursor,
        has_more=has_more,
    )