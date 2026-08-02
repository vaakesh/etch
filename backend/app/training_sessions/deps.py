from typing import Annotated

from app.deps import UoWFactory, get_uow_factory
from app.training_sessions.service import TrainingSessionService
from fastapi import Depends


def get_training_session_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> TrainingSessionService:
    return TrainingSessionService(
        uow_factory=uow_factory,
    )

TrainingSessionServiceDeps = Annotated[
    TrainingSessionService,
    Depends(get_training_session_service),
]