from fastapi import Depends

from app.deps import UoWFactory, get_uow_factory
from app.users.service import UserService



def get_user_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> UserService:
    return UserService(
        uow_factory=uow_factory,
    )