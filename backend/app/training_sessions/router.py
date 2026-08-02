from uuid import UUID

from app.auth.deps import CurrentUser, OptionalCurrentUser
from app.training_sessions.deps import (
    TrainingSessionServiceDeps,
)
from app.training_sessions.schemas import (
    SubmitAnswerResponse,
    TrainingSessionOut,
    UserAnswer,
)
from fastapi import APIRouter, Path

router = APIRouter(prefix="/training-sessions")


@router.get(
    "/{session_uuid}", 
    response_model=TrainingSessionOut,
)
async def get_training_session(
    session_uuid: UUID,
    current_user: OptionalCurrentUser,
    training_session_service: TrainingSessionServiceDeps,
):
    training_session = await training_session_service.get_by_uuid(
        session_uuid=session_uuid,
        current_user_id=current_user.id if current_user else None,
    )
    return training_session

@router.put(
        "/{training_session_uuid}/items/{sequence_number}/submit",
        response_model=SubmitAnswerResponse,
)
async def submit_answer(
    training_session_uuid: UUID,
    user_answer: UserAnswer,
    current_user: CurrentUser,
    training_session_service: TrainingSessionServiceDeps,
    sequence_number: int = Path(ge=1),
):
    return await training_session_service.submit_answer(
        user_id=current_user.id,
        training_session_uuid=training_session_uuid,
        sequence_number=sequence_number,
        user_answer=user_answer,
    )