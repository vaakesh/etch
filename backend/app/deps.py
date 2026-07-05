from collections.abc import AsyncGenerator
import logging
from typing import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.service import UnitOfWork
from app.database import get_async_session_maker


UoWFactory = Callable[[], UnitOfWork]

def get_uow_factory(
    session_maker: async_sessionmaker[AsyncSession] = Depends(get_async_session_maker),
) -> UoWFactory:
    def factory() -> UnitOfWork:
        return UnitOfWork(session_maker)
    return factory
