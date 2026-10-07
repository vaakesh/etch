from datetime import datetime
import logging
from pydantic import UUID7

from app.auth.cookies import clear_tokens_cookie
from app.auth.deps import CurrentUser, CurrentUserWithSettings, OptionalCurrentUser
from app.cards.deps import CardServiceDeps
from app.cards.schemas import CardResponse
from app.common.schemas import CursorPage
from app.common.types import PageLimit, PaginationCursor, SearchQuery, Username
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
    CreateUserRequest,
    PrivateUserResponse,
    UpdateUserRequest,
    UserProfileResponse,
    UserSettingsResponse,
    UpdateUserSettingsRequest,
)
from fastapi import APIRouter, Depends, Query, Response, status
from app.tracing import traced, trace_span

from app.redis.rate_limiters import (
    profile_rate_limit,
    public_users_rate_limit,
    registration_rate_limit,
    users_rate_limit,
)

router = APIRouter(prefix="/users")
logger = logging.getLogger(__name__)

@router.get(
    "/me",
    response_model=PrivateUserResponse,
    dependencies=[Depends(profile_rate_limit)],
)
async def get_me(
    current_user: CurrentUserWithSettings,
):
    return PrivateUserResponse.from_user_with_settings(
        user=current_user,
    )

# checked
@router.post(
    "/create",
    response_model=PrivateUserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(registration_rate_limit)],
)
@traced("users.router.create_user")
async def create_user(
    payload: CreateUserRequest,
    user_service: UserServiceDeps,
):
    new_user = await user_service.create_user(payload)
    with trace_span("users.router.create_user.build_response"):
        return PrivateUserResponse.from_user_with_settings(
            user=new_user,
        )

# checked
@router.patch(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=PrivateUserResponse,
    dependencies=[Depends(users_rate_limit)],
)
@traced("users.router.update_user")
async def update_user(
    payload: UpdateUserRequest,
    current_user: CurrentUser,
    user_service: UserServiceDeps,
):
    return await user_service.update_user(
        current_user_id=current_user.id,
        payload=payload,
    )

@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(users_rate_limit)],
)
@traced("users.router.delete_user")
async def delete_user(
    response: Response,
    current_user: CurrentUser,
    user_service: UserServiceDeps,
) -> None:
    await user_service.delete_user(
        current_user_id=current_user.id,
    )
    clear_tokens_cookie(response=response)

# checked
@router.patch(
    "/me/settings",
    status_code=status.HTTP_200_OK,
    response_model=UserSettingsResponse,
    dependencies=[Depends(users_rate_limit)],
)
@traced("users.router.update_settings")
async def update_settings(
    current_user: CurrentUser,
    user_service: UserServiceDeps,
    payload: UpdateUserSettingsRequest,
):
    return await user_service.update_user_settings(
        current_user_id=current_user.id,
        payload=payload,
    )

@router.get(
    path="/profile/{username}",
    dependencies=[Depends(public_users_rate_limit)],
    response_model=UserProfileResponse,
)
@traced("users.router.get_user_profile")
async def get_user_profile(
    username: Username,
    current_user: OptionalCurrentUser,
    user_service: UserServiceDeps,
):
    return await user_service.get_user_profile(
        viewer_id=current_user.id if current_user else None,
        username=username,
    )

@router.get(
    "/me/daily-activity",
    dependencies=[Depends(users_rate_limit)],
)
@traced("users.router.get_user_daily_activity")
async def get_user_daily_activity(
    current_user: CurrentUser,
    training_session_service: TrainingSessionServiceDeps,
    from_datetime: datetime,
    to_datetime: datetime | None = None,
):
    return await training_session_service.get_user_activity(
        user_id=current_user.id,
        from_datetime=from_datetime,
        to_datetime=to_datetime,
    )

@router.get(
    "/me/decks",
    response_model=CursorPage[DeckResponse],
    dependencies=[Depends(users_rate_limit)],
)
@traced("users.router.get_my_decks")
async def get_my_decks(
    current_user: CurrentUser,
    deck_service: DeckServiceDeps,
    limit: PageLimit = 30,
    search_query: SearchQuery = None,
    cursor: PaginationCursor = None,
):
    page = await deck_service.get_owned_decks(
        owner_id=current_user.id,
        search_query=search_query,
        cursor=cursor,
        limit=limit,
    )

    return CursorPage[DeckResponse](
        items=page.items,
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )

@router.get(
    "/me/training-sessions",
    response_model=CursorPage[TrainingSessionResponse],
    dependencies=[Depends(users_rate_limit)],
)
@traced("users.router.get_my_training_sessions")
async def get_my_training_sessions(
    current_user: CurrentUser,
    training_session_service: TrainingSessionServiceDeps,
    limit: PageLimit = 20,
    status: TrainingSessionStatus | None = None,
    cursor: PaginationCursor = None,
):
    training_sessions, next_cursor, has_more = (
        await training_session_service.get_sessions_by_user_uuid(
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
@traced("users.router.get_my_saved_decks")
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
    "/{user_uuid}/decks",
    response_model=CursorPage[DeckResponse],
    dependencies=[Depends(public_users_rate_limit)],
)
@traced("users.router.get_public_decks_by_user")
async def get_public_decks_by_user(
    user_uuid: UUID7,
    current_user: OptionalCurrentUser,
    deck_service: DeckServiceDeps,
    search_query: SearchQuery = None,
    cursor: PaginationCursor = None,
    limit: PageLimit = 30,
):
    page = await deck_service.get_public_by_owner_uuid(
        owner_uuid=user_uuid,
        viewer_id=current_user.id if current_user else None,
        search_query=search_query,
        cursor=cursor,
        limit=limit,
    )

    return CursorPage[DeckResponse](
        items=page.items,
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )
