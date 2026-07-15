from fastapi import Request, Response

from app.auth.deps import get_auth_tokens_service
from app.auth.errors import RefreshTokenNotFoundError


def set_tokens_cookie(access_token: str, refresh_token: str, response: Response) -> None:
    """
    sets access and refresh tokens in cookie
    """
    auth_token_config = get_auth_tokens_service().config
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * auth_token_config.access_token_expire_minutes,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * auth_token_config.refresh_token_expire_days,
    )


def clear_tokens_cookie(response: Response) -> None:
    """
    removes tokens from cookie
    """
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key="refresh_token",
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def get_refresh_cookie(request: Request) -> str:
    """
    gets refresh token from cookie or raises error
    """
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token is None:
        raise RefreshTokenNotFoundError()

    return refresh_token