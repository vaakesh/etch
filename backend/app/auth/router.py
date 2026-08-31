






from fastapi.security import OAuth2PasswordRequestForm

from app.auth.cookies import clear_tokens_cookie, get_refresh_cookie, set_tokens_cookie
from app.auth.deps import AuthServiceDeps, CurrentUser
from app.auth.schemas import AccessTokenResponse, LoginRequest, AuthSessionResponse
from app.redis.rate_limiters import (
    auth_actions_rate_limit,
    auth_sessions_rate_limit,
    login_rate_limit,
)
from fastapi import APIRouter, Depends, Request, Response, status

router = APIRouter(prefix="/auth")

@router.post("/token", dependencies=[Depends(login_rate_limit)])
async def login_for_bearer_token(
    auth_service: AuthServiceDeps,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> AccessTokenResponse:
    bearer_token = await auth_service.login_by_bearer_token_without_refresh(
        username=form_data.username,
        password=form_data.password,
    )
    return bearer_token

@router.post(
    "/login",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(login_rate_limit)],
)
async def login(
    form_data: LoginRequest,
    auth_service: AuthServiceDeps,
) -> None:
    tokens = await auth_service.login(
        username=form_data.username, 
        password=form_data.password,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_tokens_cookie(tokens.access_token, tokens.refresh_token, response)
    return response

@router.post("/logout", dependencies=[Depends(auth_actions_rate_limit)])
async def logout(
    response: Response,
    request: Request,
    auth_service: AuthServiceDeps,
) -> None:
    refresh_token = request.cookies.get("refresh_token")
    await auth_service.logout(refresh_token)
    clear_tokens_cookie(response)

@router.post(
    "/refresh",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth_actions_rate_limit)],
)
async def refresh(
    request: Request,
    response: Response,
    auth_service: AuthServiceDeps,
) -> None:
    tokens = await auth_service.refresh(get_refresh_cookie(request))
    set_tokens_cookie(tokens.access_token, tokens.refresh_token, response)


@router.get(
    "/sessions",
    response_model=list[AuthSessionResponse],
    dependencies=[Depends(auth_sessions_rate_limit)],
)
async def get_sessions(
    user: CurrentUser,
    auth_service: AuthServiceDeps,
) -> list[AuthSessionResponse]:
    sessions = await auth_service.get_all_user_sessions(user.id)
    return sessions
