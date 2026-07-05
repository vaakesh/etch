from fastapi import Depends

from app.deps import get_uow_factory, UoWFactory

from app.cards.service import CardService


def get_card_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> CardService:
    return CardService(
        uow_factory=uow_factory,
    )