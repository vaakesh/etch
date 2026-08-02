from typing import Annotated

from app.deps import UoWFactory, get_uow_factory
from app.users.service import UserService
from fastapi import Depends


def get_user_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> UserService:
    return UserService(
        uow_factory=uow_factory,
    )

UserServiceDeps = Annotated[
    UserService,
    Depends(get_user_service),
]