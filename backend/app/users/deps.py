from typing import Annotated

from app.deps import UoWFactory, get_uow_factory
from app.users.service import UserService
from fastapi import Depends

from app.redis.deps import CacheInvalidatorDeps, CacheServiceDeps
from app.tracing import traced


def get_user_service(
    cache_service: CacheServiceDeps,
    cache_invalidator: CacheInvalidatorDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> UserService:
    return UserService(
        uow_factory=uow_factory,
        cache_service=cache_service,
        cache_invalidator=cache_invalidator,
    )

UserServiceDeps = Annotated[
    UserService,
    Depends(get_user_service),
]
