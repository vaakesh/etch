


from functools import lru_cache
from uuid import UUID

from fastapi import Depends, Request

from app.auth.service import AuthService, AuthTokensService
from app.config import get_auth_tokens_config
from app.deps import UoWFactory, get_uow_factory
from app.auth.errors import AccessTokenNotFoundError
from app.users.deps import get_user_service
from app.users.models import User
from app.users.service import UserService


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

async def get_current_user(
        request: Request,
        user_service: UserService = Depends(get_user_service),
        auth_tokens_service: AuthTokensService = Depends(get_auth_tokens_service),
) -> User:
    access_token = request.cookies.get("access_token")

    if access_token is None:
        raise AccessTokenNotFoundError()
    
    payload = auth_tokens_service.decode_access_token(access_token)
    user_uuid = UUID(payload.get("sub"))

    user = await user_service.get_by_uuid(user_uuid)
    return user