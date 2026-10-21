import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, StringConstraints

from rag.dependencies import (
    clear_dependency_caches,
    get_ask_lock,
    get_rag_service,
    get_resources,
)
from rag.errors import RagError
from rag.service import RagService
from rag.types import Answer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


class AskRequest(BaseModel):
    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    resources = get_resources()
    resources.callback(clear_dependency_caches)

    try:
        service = get_rag_service()
        get_ask_lock()

        await run_in_threadpool(service.index)
        yield
    finally:
        resources.close()


app = FastAPI(lifespan=lifespan)

@app.post("/ask", response_model=Answer)
async def ask(
    body: AskRequest,
    service: Annotated[RagService, Depends(get_rag_service)],
) -> Answer:
    lock = get_ask_lock()

    if lock.locked():
        raise HTTPException(
            status_code=503,
            detail="Assistant is busy. Try again later.",
        )

    async with lock:
        try:
            return await run_in_threadpool(service.ask, body.message)
        except RagError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
