from typing import Annotated

from pydantic import BaseModel, StringConstraints


class AskRequest(BaseModel):
    message: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=200,
        )
    ]


class AskSource(BaseModel):
    chunk_id: str
    title: str
    text: str
    source: str
    score: float
    rerank_score: float


class AskResponse(BaseModel):
    text: str
    sources: list[AskSource]


class AskMessageResponse(BaseModel):
    text: str
