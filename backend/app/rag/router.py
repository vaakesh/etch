from fastapi import APIRouter, Depends

from app.rag.deps import RagClientDeps
from app.rag.schemas import AskMessageResponse, AskRequest
from app.redis.rate_limiters import ask_rate_limit

router = APIRouter(tags=["assistant"])


@router.post(
    "/ask",
    response_model=AskMessageResponse,
    dependencies=[Depends(ask_rate_limit)],
)
async def ask(
    payload: AskRequest,
    rag: RagClientDeps,
) -> AskMessageResponse:
    return await rag.ask(payload.message)
