from typing import Annotated

from app.deps import UoWFactory, get_uow_factory
from app.users.service import UserService
from fastapi import Depends

from app.redis.deps import CacheServiceDeps


def get_user_service(
    cache_service: CacheServiceDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> UserService:
    return UserService(
        uow_factory=uow_factory,
        cache_service=cache_service,
    )

UserServiceDeps = Annotated[
    UserService,
    Depends(get_user_service),
]