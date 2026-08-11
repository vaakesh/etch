from typing import Annotated

from app.decks.service import DeckService, UserDeckService
from app.deps import UoWFactory, get_uow_factory
from fastapi import Depends

from app.redis.deps import CacheServiceDeps


def get_deck_service(
    cache_service: CacheServiceDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> DeckService:
    return DeckService(
        uow_factory=uow_factory,
        cache_service=cache_service,
    )

def get_user_deck_service(
    cache_service: CacheServiceDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> UserDeckService:
    return UserDeckService(
        uow_factory=uow_factory,
        cache_service=cache_service,
    )

DeckServiceDeps = Annotated[
    DeckService,
    Depends(get_deck_service),
]
UserDeckServiceDeps = Annotated[
    UserDeckService,
    Depends(get_user_deck_service),
]