






from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.service import AuthService
from app.auth.deps import get_auth_service, get_current_user
from app.auth.schemas import SessionOut
from app.auth.cookies import clear_tokens_cookie, get_refresh_cookie, set_tokens_cookie
from app.users.models import User


router = APIRouter(prefix="/auth")

@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    tokens = await auth_service.login(username=form_data.username, password=form_data.password)
    set_tokens_cookie(tokens.access_token, tokens.refresh_token, response)

@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    refresh_token = request.cookies.get("refresh_token")
    await auth_service.logout(refresh_token)
    clear_tokens_cookie(response)

@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
async def refresh(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    tokens = await auth_service.refresh(get_refresh_cookie(request))
    set_tokens_cookie(tokens.access_token, tokens.refresh_token, response)


@router.get("/sessions", response_model=list[SessionOut])
async def get_sessions(
    user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[SessionOut]:
    sessions = await auth_service.get_all_user_sessions(user.id)
    return [SessionOut.model_validate(session) for session in sessions]
