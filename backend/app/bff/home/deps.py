




from fastapi import Depends

from app.bff.home.service import BffService
from app.decks.service import DeckService
from app.deps import UoWFactory, get_uow_factory


def get_bff_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> BffService:
    return BffService(
        uow_factory=uow_factory,
    )