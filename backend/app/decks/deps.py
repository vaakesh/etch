from fastapi import Depends

from app.deps import get_uow_factory, UoWFactory

from app.decks.service import DeckService, UserDeckService


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