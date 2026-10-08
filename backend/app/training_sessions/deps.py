from typing import Annotated

from app.deps import UoWFactory, get_uow_factory
from app.training_sessions.service import TrainingSessionService
from fastapi import Depends

from app.redis.deps import CacheInvalidatorDeps
from app.tracing import traced


def get_training_session_service(
    cache_invalidator: CacheInvalidatorDeps,
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> TrainingSessionService:
    return TrainingSessionService(
        uow_factory=uow_factory,
        cache_invalidator=cache_invalidator,
    )

TrainingSessionServiceDeps = Annotated[
    TrainingSessionService,
    Depends(get_training_session_service),
]
