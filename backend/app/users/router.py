from datetime import datetime
from uuid import UUID

from app.auth.cookies import clear_tokens_cookie
from app.auth.deps import AuthServiceDeps, CurrentUser, CurrentUserWithSettings
from app.cards.deps import CardServiceDeps
from app.cards.schemas import CardResponse
from app.common.schemas import CursorPage
from app.common.types import PageLimit, PaginationCursor, SearchQuery
from app.decks.deps import DeckServiceDeps, UserDeckServiceDeps
from app.decks.schemas import DeckListItemResponse, DeckResponse
from app.training_sessions.deps import (
    TrainingSessionServiceDeps,
)
from app.training_sessions.models import TrainingSessionStatus
from app.training_sessions.schemas import (
    TrainingSessionResponse,
)
from app.users.deps import UserServiceDeps
from app.users.schemas import (
    ChangePasswordRequest,
    CreateUserRequest,
    PrivateUserResponse,
    PublicUserResponse,
    UpdateUserRequest,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from fastapi import APIRouter, Depends, Query, Response, status

from app.redis.rate_limiters import (
    password_change_rate_limit,
    profile_rate_limit,
    public_users_rate_limit,
    registration_rate_limit,
    users_rate_limit,
)

router = APIRouter(prefix="/users")

@router.get(
    "/me",
    response_model=PrivateUserResponse,
    dependencies=[Depends(profile_rate_limit)],
)
async def get_me(
    current_user: CurrentUserWithSettings,
):
    return PrivateUserResponse(
        uuid=current_user.uuid,
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        settings=UserSettingsResponse(
            locale=current_user.settings.locale,
            theme=current_user.settings.theme,
            show_previews_for_long=current_user.settings.show_previews_for_long,
        )
    )

@router.get(
    "/me/daily-activity",
    dependencies=[Depends(users_rate_limit)],
)
async def get_user_daily_activity(
    current_user: CurrentUser,
    training_session_service: TrainingSessionServiceDeps,
    from_date: datetime,
    to_date: datetime | None = None,
):
    return await training_session_service.user_daily_activity(
        user_id=current_user.id,
        from_date=from_date,
        to_date=to_date,
    )

@router.patch(
    "/me/settings",
    response_model=UserSettingsResponse,
    dependencies=[Depends(users_rate_limit)],
)
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

@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(password_change_rate_limit)],
)
async def change_password(
    payload: ChangePasswordRequest,
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

@router.get(
    "/me/decks",
    response_model=CursorPage[DeckResponse],
    dependencies=[Depends(users_rate_limit)],
)
async def get_my_decks(
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
    limit: PageLimit = 30,
    search_query: SearchQuery = None,
    cursor: PaginationCursor = None,
):
    decks, next_cursor, has_more = await deck_service.get_all_by_user_uuid(
        user_uuid=current_user.uuid,
        search_query=search_query,
        cursor=cursor,
        limit=limit,
        public_only=False,
        current_user_id=current_user.id,
    )

    return CursorPage[DeckResponse](
        items=decks,
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get(
    "/me/cards",
    response_model=CursorPage[CardResponse],
    dependencies=[Depends(users_rate_limit)],
)
async def get_my_cards(
    current_user: CurrentUser,
    card_service: CardServiceDeps,
    search_query: SearchQuery = None,
    limit: PageLimit = 50,
    cursor: PaginationCursor = None,
):
    cards, next_cursor, has_more = await card_service.get_all_by_user_id(
        user_id=current_user.id,
        search_query=search_query,
        cursor=cursor,
        limit=limit,
    )

    return CursorPage[CardResponse](
        items=cards,
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get(
    "/me/training-sessions",
    response_model=CursorPage[TrainingSessionResponse],
    dependencies=[Depends(users_rate_limit)],
)
async def get_my_training_sessions(
    current_user: CurrentUser,
    training_session_service: TrainingSessionServiceDeps,
    limit: PageLimit = 20,
    status: TrainingSessionStatus | None = None,
    cursor: PaginationCursor = None,
):
    training_sessions, next_cursor, has_more = (
        await training_session_service.get_all_by_user_uuid(
            user_uuid=current_user.uuid,
            status=status,
            cursor=cursor,
            limit=limit,
        )
    )
    return CursorPage[TrainingSessionResponse](
        items=training_sessions,
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get(
    "/me/decks/saved",
    response_model=list[DeckListItemResponse],
    dependencies=[Depends(users_rate_limit)],
)
async def get_my_saved_decks(
    current_user: CurrentUser,
    user_deck_service: UserDeckServiceDeps,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[DeckListItemResponse]:
    saved_decks = await user_deck_service.get_page_of_saved_decks_by_user_id(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )

    return saved_decks

@router.get(
    "/{user_uuid}",
    response_model=PublicUserResponse,
    dependencies=[Depends(public_users_rate_limit)],
)
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
    response_model=PrivateUserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(registration_rate_limit)],
)
async def create_user(
    payload: CreateUserRequest,
    user_service: UserServiceDeps,
):
    new_user, user_settings = await user_service.create_user(payload)
    return PrivateUserResponse(
        uuid=new_user.uuid,
        username=new_user.username,
        email=new_user.email,
        created_at=new_user.created_at,
        updated_at=new_user.updated_at,
        settings=UserSettingsResponse(
            locale=user_settings.locale,
            theme=user_settings.theme,
            show_previews_for_long=user_settings.show_previews_for_long,
        )
    )

@router.patch(
    "/me",
    response_model=PrivateUserResponse,
    dependencies=[Depends(users_rate_limit)],
)
async def update_user(
    payload: UpdateUserRequest,
    current_user: CurrentUser,
    user_service: UserServiceDeps,
):
    updated_user = await user_service.update_user(
        target_user_uuid=current_user.uuid,
        current_user_id=current_user.id,
        payload=payload,
    )
    return PrivateUserResponse(
        uuid=updated_user.uuid,
        username=updated_user.username,
        email=updated_user.email,
        created_at=updated_user.created_at,
        updated_at=updated_user.updated_at,
        settings=UserSettingsResponse(
            locale=updated_user.settings.locale,
            theme=updated_user.settings.theme,
            show_previews_for_long=updated_user.settings.show_previews_for_long,
        )
    )

@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(users_rate_limit)],
)
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
    response_model=CursorPage[TrainingSessionResponse],
    dependencies=[Depends(public_users_rate_limit)],
)
async def get_public_training_sessions_by_user(
    user_uuid: UUID,
    training_session_service: TrainingSessionServiceDeps,
    cursor: PaginationCursor = None,
    limit: PageLimit = 20,
):
    training_sessions, next_cursor, has_more = (
        await training_session_service.get_all_by_user_uuid(
            user_uuid=user_uuid,
            status=TrainingSessionStatus.COMPLETED,
            cursor=cursor,
            limit=limit,
        )
    )
    return CursorPage[TrainingSessionResponse](
        items=training_sessions,
        next_cursor=next_cursor,
        has_more=has_more,
    )

@router.get(
    "/{user_uuid}/decks",
    response_model=CursorPage[DeckResponse],
    dependencies=[Depends(public_users_rate_limit)],
)
async def get_public_decks_by_user(
    user_uuid: UUID,
    deck_service: DeckServiceDeps,
    search_query: SearchQuery = None,
    cursor: PaginationCursor = None,
    limit: PageLimit = 30,
):
    decks, next_cursor, has_more = await deck_service.get_all_by_user_uuid(
        user_uuid=user_uuid,
        search_query=search_query,
        cursor=cursor,
        limit=limit,
        public_only=True,
        current_user_id=None,
    )

    return CursorPage[DeckResponse](
        items=decks,
        next_cursor=next_cursor,
        has_more=has_more,
    )
