from typing import Annotated

from app.deps import UoWFactory, get_uow_factory
from app.training_sessions.service import TrainingSessionService
from fastapi import Depends

from app.redis.deps import CacheServiceDeps


def get_training_session_service(
    cache_service: CacheServiceDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> TrainingSessionService:
    return TrainingSessionService(
        uow_factory=uow_factory,
        cache_service=cache_service,
    )

TrainingSessionServiceDeps = Annotated[
    TrainingSessionService,
    Depends(get_training_session_service),
]