from math import isfinite
from typing import TYPE_CHECKING

import httpx

from rag.errors import RagError
from rag.types import RerankedHit, SearchHit

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        dtype: str,
        batch_size: int,
        max_length: int,
    ) -> None:
        """Store explicit model settings without loading weights until the first request."""
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")
        if max_length <= 0:
            raise ValueError("max_length must be greater than zero.")
        self._model_name = model_name
        self._device = device
        self._dtype = dtype
        self._batch_size = batch_size
        self._max_length = max_length
        self._model: CrossEncoder | None = None

    def _load_model(self) -> "CrossEncoder":
        """Load the cross-encoder once and keep its raw relevance logits for ranking."""
        from sentence_transformers import CrossEncoder
        from torch.nn import Identity

        if self._model is not None:
            return self._model
        try:
            self._model = CrossEncoder(
                self._model_name,
                local_files_only=True,
                device=self._device,
                model_kwargs={"dtype": self._dtype},
                max_length=self._max_length,
                activation_fn=Identity(),
            )
        except (OSError, ValueError, RuntimeError, httpx.HTTPError) as exc:
            raise RagError(f"Failed to load reranking model {self._model_name}: {exc}") from exc
        return self._model

    def rerank(self, question: str, candidates: list[SearchHit], *, k: int) -> list[RerankedHit]:
        """Score question-fragment pairs and return the best k, preserving retrieval scores."""
        question = question.strip()
        if not question:
            raise ValueError("Question must not be empty.")
        if k <= 0:
            raise ValueError("k must be greater than zero.")
        if not candidates:
            return []

        model = self._load_model()
        pairs = [(question, candidate.text) for candidate in candidates]
        try:
            scores = [
                float(score)
                for score in model.predict(
                    pairs,
                    batch_size=self._batch_size,
                    show_progress_bar=False,
                )
            ]
        except (OSError, TypeError, ValueError, RuntimeError, httpx.HTTPError) as exc:
            raise RagError(f"Failed to rerank fragments: {exc}") from exc
        if len(scores) != len(candidates) or any(not isfinite(score) for score in scores):
            raise RagError("Reranking model must return one finite score per candidate.")

        ranked = sorted(
            zip(candidates, scores, strict=True), key=lambda item: item[1], reverse=True
        )
        return [
            RerankedHit(
                chunk_id=candidate.chunk_id,
                title=candidate.title,
                text=candidate.text,
                source=candidate.source,
                score=candidate.score,
                rerank_score=score,
            )
            for candidate, score in ranked[:k]
        ]
