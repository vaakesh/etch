


from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi.security import OAuth2PasswordBearer

from app.auth.errors import AccessTokenNotFoundError
from app.auth.service import AuthService, AuthTokensService
from app.config import get_auth_tokens_config
from app.deps import UoWFactory, get_uow_factory
from app.users.deps import UserServiceDeps, get_user_service
from app.users.models import User
from app.users.service import UserService
from fastapi import Depends, Request


@lru_cache
def get_auth_tokens_service() -> AuthTokensService:
    return AuthTokensService(get_auth_tokens_config())

def get_auth_service(
        auth_tokens_service: AuthTokensService = Depends(get_auth_tokens_service),
        uow_factory: UoWFactory = Depends(get_uow_factory)
) -> AuthService:
    return AuthService(
        uow_factory=uow_factory, 
        auth_tokens_service=auth_tokens_service
    )

# auto_error = False, чтобы не выкидывалась ошибка, если bearer токен не найден
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)
async def get_bearer_token(
    token: str = Depends(oauth2_scheme)
) -> str | None:
    return token


async def auth_user(
    request: Request,
    bearer_token: str | None = Depends(get_bearer_token),
) -> str | None:
    if bearer_token is not None:
        return bearer_token
    
    access_token = request.cookies.get("access_token")
    
    return access_token

async def get_current_user(
    request: Request,
    user_service: UserService = Depends(get_user_service),
    access_token: str | None = Depends(auth_user),
    auth_tokens_service: AuthTokensService = Depends(get_auth_tokens_service),
) -> User: 
    if access_token is None:
        raise AccessTokenNotFoundError()
    
    payload = auth_tokens_service.decode_access_token(access_token)
    user_uuid = UUID(payload.get("sub"))

    user = await user_service.get_by_uuid(user_uuid)
    return user

async def get_optional_current_user(
    request: Request,
    user_service: UserServiceDeps,
    access_token: str | None = Depends(auth_user),
    auth_tokens_service: AuthTokensService = Depends(get_auth_tokens_service),
) -> User | None:
    if access_token is None:
        return None

    return await get_current_user(
        request=request,
        user_service=user_service,
        access_token=access_token,
        auth_tokens_service=auth_tokens_service,
    )

type AuthServiceDeps = Annotated[
    AuthService,
    Depends(get_auth_service),
]

type CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]

type OptionalCurrentUser = Annotated[
    User | None,
    Depends(get_optional_current_user),
]
