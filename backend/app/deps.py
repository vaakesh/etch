from collections.abc import Callable
from secrets import compare_digest
from typing import Annotated

from app.config import Settings, get_settings
from app.database import get_async_session_maker
from app.errors import MetricsAccessDeniedError
from app.service import UnitOfWork
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

UoWFactory = Callable[[], UnitOfWork]

def get_uow_factory(
    session_maker: async_sessionmaker[AsyncSession] = Depends(get_async_session_maker),
) -> UoWFactory:
    def factory() -> UnitOfWork:
        return UnitOfWork(session_maker)
    return factory


metrics_bearer = HTTPBearer(auto_error=False)


async def require_metrics_access(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(metrics_bearer),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if credentials is None or not settings.metrics_token.strip():
        raise MetricsAccessDeniedError()

    if not compare_digest(
        credentials.credentials.encode("utf-8"),
        settings.metrics_token.encode("utf-8"),
    ):
        raise MetricsAccessDeniedError()
