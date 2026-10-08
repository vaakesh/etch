from typing import Annotated

from app.cards.service import CardService
from app.deps import UoWFactory, get_uow_factory
from fastapi import Depends

from app.redis.deps import CacheInvalidatorDeps, CacheServiceDeps
from app.tracing import traced


@traced("cards.deps.get_card_service")
def get_card_service(
    cache_service: CacheServiceDeps,
    cache_invalidator: CacheInvalidatorDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> CardService:
    return CardService(
        uow_factory=uow_factory,
        cache_service=cache_service,
        cache_invalidator=cache_invalidator,
    )

CardServiceDeps = Annotated[
    CardService,
    Depends(get_card_service),
]
