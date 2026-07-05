from fastapi import Depends

from app.deps import get_uow_factory, UoWFactory

from app.decks.service import DeckService


def get_deck_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> DeckService:
    return DeckService(
        uow_factory=uow_factory,
    )