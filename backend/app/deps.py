from collections.abc import Callable

from app.database import get_async_session_maker
from app.service import UnitOfWork
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

UoWFactory = Callable[[], UnitOfWork]

def get_uow_factory(
    session_maker: async_sessionmaker[AsyncSession] = Depends(get_async_session_maker),
) -> UoWFactory:
    def factory() -> UnitOfWork:
        return UnitOfWork(session_maker)
    return factory
