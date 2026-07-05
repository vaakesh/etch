from fastapi import Depends

from app.deps import UoWFactory, get_uow_factory
from app.training_sessions.service import TrainingSessionService




def get_training_session_service(
    uow_factory: UoWFactory = Depends(get_uow_factory),
) -> TrainingSessionService:
    return TrainingSessionService(
        uow_factory=uow_factory,
    )