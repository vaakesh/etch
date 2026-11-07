from typing import Annotated

from fastapi import Depends

from app.decks.service import DeckService, UserDeckService
from app.deps import UoWFactory, get_uow_factory
from app.redis.deps import CacheInvalidatorDeps, CacheServiceDeps


def get_deck_service(
    cache_service: CacheServiceDeps,
    cache_invalidator: CacheInvalidatorDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> DeckService:
    return DeckService(
        uow_factory=uow_factory,
        cache_service=cache_service,
        cache_invalidator=cache_invalidator,
    )


def get_user_deck_service(
    cache_service: CacheServiceDeps,
    cache_invalidator: CacheInvalidatorDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> UserDeckService:
    return UserDeckService(
        uow_factory=uow_factory,
        cache_service=cache_service,
        cache_invalidator=cache_invalidator,
    )


DeckServiceDeps = Annotated[
    DeckService,
    Depends(get_deck_service),
]
UserDeckServiceDeps = Annotated[
    UserDeckService,
    Depends(get_user_deck_service),
]
