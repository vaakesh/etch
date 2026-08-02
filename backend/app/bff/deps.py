




from app.bff.service import BffService
from app.deps import UoWFactory, get_uow_factory
from fastapi import Depends


def get_bff_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> BffService:
    return BffService(
        uow_factory=uow_factory,
    )