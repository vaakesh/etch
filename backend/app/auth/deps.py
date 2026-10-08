


from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi.security import OAuth2PasswordBearer

from app.auth.errors import AccessTokenNotFoundError
from app.auth.schemas import ClientInfo
from app.auth.service import AuthService, AuthTokensService
from app.config import get_auth_tokens_config
from app.deps import UoWFactory, get_uow_factory
from app.redis.deps import CacheInvalidatorDeps
from app.users.deps import UserServiceDeps, get_user_service
from app.users.models import User
from app.users.service import UserService
from fastapi import Depends, Request

from app.users.schemas import InternalUser, InternalUserWithSettings


@lru_cache
def get_auth_tokens_service() -> AuthTokensService:
    return AuthTokensService(get_auth_tokens_config())

def get_auth_service(
        cache_invalidator: CacheInvalidatorDeps,
        auth_tokens_service: AuthTokensService = Depends(get_auth_tokens_service),
        uow_factory: UoWFactory = Depends(get_uow_factory)
) -> AuthService:
    return AuthService(
        uow_factory=uow_factory,
        auth_tokens_service=auth_tokens_service,
        cache_invalidator=cache_invalidator,
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

async def get_current_user_uuid(
    access_token: str | None = Depends(auth_user),
    auth_tokens_service: AuthTokensService = Depends(get_auth_tokens_service),
) -> UUID | None:
    if access_token is None:
        return None

    payload = auth_tokens_service.decode_access_token(access_token)
    user_uuid = UUID(payload["sub"])
    return user_uuid

async def get_current_user(
    user_service: UserService = Depends(get_user_service),
    user_uuid: UUID | None = Depends(get_current_user_uuid),
) -> InternalUser:
    if user_uuid is None:
        raise AccessTokenNotFoundError()
    return await user_service.get_by_uuid(
        user_uuid=user_uuid,
    )
    

async def get_current_user_with_settings(
    user_service: UserService = Depends(get_user_service),
    user_uuid: UUID | None = Depends(get_current_user_uuid),
) -> InternalUserWithSettings: 
    if user_uuid is None:
        raise AccessTokenNotFoundError()
    return await user_service.get_by_uuid_with_settings(user_uuid)
    

async def get_optional_current_user(
    request: Request,
    user_service: UserServiceDeps,
    user_uuid: UUID | None = Depends(get_current_user_uuid),
) -> InternalUser | None:
    if user_uuid is None:
        return None
    return await user_service.get_by_uuid(
        user_uuid=user_uuid,
    )

MAX_CLIENT_IP_LENGTH = 64
MAX_USER_AGENT_LENGTH = 512

async def get_client_info(request: Request) -> ClientInfo:
    # Behind the reverse proxy uvicorn already put the forwarded address here.
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return ClientInfo(
        ip=ip[:MAX_CLIENT_IP_LENGTH] if ip else None,
        user_agent=user_agent[:MAX_USER_AGENT_LENGTH] if user_agent else None,
    )

type AuthServiceDeps = Annotated[
    AuthService,
    Depends(get_auth_service),
]

type ClientInfoDeps = Annotated[
    ClientInfo,
    Depends(get_client_info),
]

type CurrentUser = Annotated[
    InternalUser,
    Depends(get_current_user),
]

type CurrentUserWithSettings = Annotated[
    InternalUserWithSettings,
    Depends(get_current_user_with_settings),
]

type OptionalCurrentUser = Annotated[
    InternalUser | None,
    Depends(get_optional_current_user),
]
