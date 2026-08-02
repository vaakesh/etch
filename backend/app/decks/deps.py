from typing import Annotated

from app.decks.service import DeckService, UserDeckService
from app.deps import UoWFactory, get_uow_factory
from fastapi import Depends


def get_deck_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> DeckService:
    return DeckService(
        uow_factory=uow_factory,
    )

def get_user_deck_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> UserDeckService:
    return UserDeckService(
        uow_factory=uow_factory,
    )

DeckServiceDeps = Annotated[
    DeckService,
    Depends(get_deck_service),
]
UserDeckServiceDeps = Annotated[
    UserDeckService,
    Depends(get_user_deck_service),
]