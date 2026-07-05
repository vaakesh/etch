from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.training_sessions.deps import get_training_session_service
from app.training_sessions.schemas import (
    TrainingSessionCreate,
    TrainingSessionFinish,
    TrainingSessionOut,
    TrainingSessionSchema,
    TrainingSessionUpdate,
)
from app.training_sessions.service import TrainingSessionService


router = APIRouter(prefix="/training-sessions")


@router.get("/", response_model=list[TrainingSessionSchema])
async def get_all_training_sessions_by_limit(
    limit: int = 10,
    training_session_service: TrainingSessionService = Depends(
        get_training_session_service
    ),
):
    return await training_session_service.get_all_training_sessions_by_limit(limit)


@router.get("/{session_uuid}", response_model=TrainingSessionSchema)
async def get_training_session(
    session_uuid: UUID,
    training_session_service: TrainingSessionService = Depends(
        get_training_session_service
    ),
):
    return await training_session_service.get_by_uuid(session_uuid)


@router.post("/", response_model=TrainingSessionOut)
async def create_training_session(
    payload: TrainingSessionCreate,
    training_session_service: TrainingSessionService = Depends(
        get_training_session_service
    ),
):
    return await training_session_service.create_training_session(payload)


@router.patch("/{session_uuid}", response_model=TrainingSessionSchema)
async def update_training_session(
    session_uuid: UUID,
    payload: TrainingSessionUpdate,
    training_session_service: TrainingSessionService = Depends(
        get_training_session_service
    ),
):
    return await training_session_service.update_training_session(
        session_uuid,
        payload,
    )


@router.patch("/{session_uuid}/finish", response_model=TrainingSessionSchema)
async def finish_training_session(
    session_uuid: UUID,
    payload: TrainingSessionFinish,
    training_session_service: TrainingSessionService = Depends(
        get_training_session_service
    ),
):
    return await training_session_service.finish_training_session(
        session_uuid,
        payload,
    )


@router.delete("/{session_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_session(
    session_uuid: UUID,
    training_session_service: TrainingSessionService = Depends(
        get_training_session_service
    ),
):
    await training_session_service.delete_training_session(session_uuid)
    return None