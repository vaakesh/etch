from dataclasses import asdict
from math import isfinite
from uuid import NAMESPACE_URL, uuid5

import httpx
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from rag.errors import IndexNotReadyError, RagError
from rag.types import Chunk, SearchHit

QDRANT_ERRORS = (ResponseHandlingException, UnexpectedResponse, httpx.TransportError)


class QdrantStore:
    def __init__(self, *, client: QdrantClient, collection: str) -> None:
        """Bind an externally owned client to the collection used for guide retrieval."""
        self._collection = collection
        self._client = client

    def rebuild(self, chunks: list[Chunk], vectors: list[list[float]], dimension: int) -> None:
        """Replace the configured collection with validated vectors and chunk metadata."""
        # Validate everything before touching the existing collection.
        if not chunks or len(chunks) != len(vectors) or dimension <= 0:
            raise RagError(
                "Chunks and embeddings must be nonempty with matching counts; "
                "dimension must be positive."
            )
        if any(len(v) != dimension or not all(isfinite(x) for x in v) for v in vectors):
            raise RagError(
                "Embeddings must have the expected dimension and contain only finite numbers."
            )
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, f"ru:{chunk.chunk_id}")),
                vector=vector,
                payload={**asdict(chunk), "lang": "ru"},
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        try:
            if self._client.collection_exists(self._collection):
                self._client.delete_collection(self._collection)
            self._client.create_collection(
                self._collection,
                vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
            )
            self._client.upsert(self._collection, points=points, wait=True)
        except QDRANT_ERRORS as exc:
            raise RagError(f"Failed to write index {self._collection} to Qdrant: {exc}") from exc

    def search(self, vector: list[float], k: int) -> list[SearchHit]:
        """Return the closest chunks from a populated, compatible collection."""
        try:
            if not self._client.collection_exists(self._collection):
                raise IndexNotReadyError("Index is missing. Run service.index() first.")
            collection = self._client.get_collection(self._collection)
            params = collection.config.params.vectors
            if (
                not isinstance(params, models.VectorParams)
                or params.size != len(vector)
                or params.distance != models.Distance.COSINE
            ):
                raise IndexNotReadyError(
                    "Index is incompatible with the embedding model. Run service.index()."
                )
            if not collection.points_count:
                raise IndexNotReadyError("Index is empty. Run service.index() first.")
            points = self._client.query_points(
                self._collection,
                query=vector,
                limit=k,
                with_payload=True,
                with_vectors=False,
            ).points
        except QDRANT_ERRORS as exc:
            raise RagError("Failed to search Qdrant. Check that the container is running.") from exc

        hits = []
        for point in points:
            payload = point.payload or {}
            fields = ("chunk_id", "title", "text", "source")
            if any(not isinstance(payload.get(field), str) for field in fields):
                raise IndexNotReadyError("Index is missing guide metadata. Run service.index().")
            hits.append(SearchHit(**{field: payload[field] for field in fields}, score=point.score))
        return hits
