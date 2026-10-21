from dataclasses import dataclass
from typing import Literal, TypedDict


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str # etch.cards.create
    title: str # "Etch: как создать карточку"
    text: str # "# Etch: как создать картоку\n\nОткройте ..."
    source: str # "content/ru/05-cards.md"


@dataclass(frozen=True)
class SearchHit(Chunk):
    score: float


@dataclass(frozen=True)
class RerankedHit(SearchHit):
    rerank_score: float


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[RerankedHit]
