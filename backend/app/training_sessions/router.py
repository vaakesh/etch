from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from app.training_sessions.deps import get_training_session_service
from app.training_sessions.schemas import (
    SubmitAnswerResponse,
    TrainingSessionCreate,
    TrainingSessionFinish,
    TrainingSessionOut,
    TrainingSessionSchema,
    TrainingSessionUpdate,
    UserAnswer,
)
from app.training_sessions.service import TrainingSessionService
from app.auth.deps import get_current_user
from app.users.models import User


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


@router.delete("/{session_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_session(
    session_uuid: UUID,
    training_session_service: TrainingSessionService = Depends(
        get_training_session_service
    ),
):
    await training_session_service.delete_training_session(session_uuid)
    return None

@router.put(
        "/{training_session_uuid}/items/{sequence_number}/submit",
        response_model=SubmitAnswerResponse,
)
async def submit_answer(
    training_session_uuid: UUID,
    user_answer: UserAnswer,
    sequence_number: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    training_session_service: TrainingSessionService = Depends(
        get_training_session_service
    ),
):
    return await training_session_service.submit_answer(
        user_id=current_user.id,
        training_session_uuid=training_session_uuid,
        sequence_number=sequence_number,
        user_answer=user_answer,
    )