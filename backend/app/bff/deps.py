




from app.bff.service import BffService
from app.deps import UoWFactory, get_uow_factory
from fastapi import Depends

from app.redis.deps import CacheInvalidatorDeps, CacheServiceDeps



def get_bff_service(
    cache_service: CacheServiceDeps,
    cache_invalidator: CacheInvalidatorDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> BffService:
    return BffService(
        uow_factory=uow_factory,
        cache_service=cache_service,
        cache_invalidator=cache_invalidator,
    )
