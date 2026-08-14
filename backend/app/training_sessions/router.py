from uuid import UUID

from app.auth.deps import CurrentUser, OptionalCurrentUser
from app.training_sessions.deps import (
    TrainingSessionServiceDeps,
)
from app.training_sessions.schemas import (
    SubmitAnswerResponse,
    TrainingSessionHistoryItemResponse,
    TrainingSessionResponse,
    UserAnswer,
)
from fastapi import APIRouter, Path, Query

router = APIRouter(prefix="/training-sessions")


@router.get(
    "/{session_uuid}", 
    response_model=TrainingSessionResponse,
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

@router.get(
    "/{session_uuid}/history",
    response_model=list[TrainingSessionHistoryItemResponse],
)
async def get_training_session_history(
    session_uuid: UUID,
    current_user: CurrentUser,
    training_session_item_service: TrainingSessionServiceDeps,
    only_answered_items: bool = False,
    page_size: int = Query(alias="ps", default=30, ge=1, le=100),
    page_number: int = Query(alias="pn", default=1, ge=1),
):
    items = await training_session_item_service.get_session_history(
        user_id=current_user.id,
        session_uuid=session_uuid,
        only_answered_items=only_answered_items,
        page_size=page_size,
        page_number=page_number,
    )
    result = [
        TrainingSessionHistoryItemResponse(
            item_uuid=item.uuid,
            sequence_number=item.sequence_number,
            prompt_text=item.prompt_text,
            answer_text=item.answer_text,
            prompt_lang=item.prompt_lang,
            answer_lang=item.answer_lang,
            user_typed_text=item.user_typed_text,
            is_answered=item.is_answered,
            is_correct=item.is_correct,
        )
        for item in items
    ]
    return result

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
