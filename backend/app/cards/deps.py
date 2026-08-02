from typing import Annotated

from app.cards.service import CardService
from app.deps import UoWFactory, get_uow_factory
from fastapi import Depends


def get_card_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> CardService:
    return CardService(
        uow_factory=uow_factory,
    )

CardServiceDeps = Annotated[
    CardService,
    Depends(get_card_service),
]