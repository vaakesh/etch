from contextlib import closing

import pytest
from qdrant_client import QdrantClient, models

from rag.errors import IndexNotReadyError, RagError
from rag.store import QdrantStore
from rag.types import Chunk, SearchHit

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    with closing(QdrantClient(":memory:")) as instance:
        yield instance


@pytest.fixture
def vector_store(client):
    return QdrantStore(client=client, collection="etch_user_guide_ru")


class TestRebuild:
    def test_replaces_deleted_documents_instead_of_appending(self, vector_store, client, chunk):
        old = Chunk("etch.cards.old", "Удалённая инструкция", "Старый текст.", "content/ru/old.md")
        vector_store.rebuild([old], [[0.0, 1.0]], 2)

        vector_store.rebuild([chunk], [[1.0, 0.0]], 2)

        assert client.count("etch_user_guide_ru").count == 1
        assert vector_store.search([1.0, 0.0], 5) == [
            SearchHit(
                chunk_id="etch.cards.create",
                title="Etch: как создать карточку",
                text="# Etch: как создать карточку\n\nНажмите «Новая карточка».",
                source="content/ru/05-cards.md",
                score=1.0,
            )
        ]

    def test_keeps_stable_ids_and_count_on_repeated_indexing(self, vector_store, client, chunk):
        vector_store.rebuild([chunk], [[1.0, 0.0]], 2)
        first_points, _ = client.scroll("etch_user_guide_ru")

        vector_store.rebuild([chunk], [[1.0, 0.0]], 2)
        second_points, _ = client.scroll("etch_user_guide_ru")

        assert len(second_points) == 1
        assert second_points[0].id == first_points[0].id
        assert second_points[0].payload["lang"] == "ru"

    @pytest.mark.parametrize("vectors", [[], [[1.0]], [[float("nan"), 0.0]]])
    def test_preserves_existing_collection_for_invalid_embeddings(
        self, vector_store, client, chunk, vectors
    ):
        vector_store.rebuild([chunk], [[1.0, 0.0]], 2)

        with pytest.raises(RagError):
            vector_store.rebuild([chunk], vectors, 2)

        assert client.count("etch_user_guide_ru").count == 1


class TestSearch:
    def test_orders_results_by_cosine_similarity(self, vector_store, chunk):
        other = Chunk("etch.cards.delete", "Удалить карточку", "Удалите карточку.", "delete.md")
        vector_store.rebuild([other, chunk], [[0.0, 1.0], [1.0, 0.0]], 2)

        hits = vector_store.search([1.0, 0.0], k=1)

        assert len(hits) == 1
        assert hits[0].chunk_id == "etch.cards.create"
        assert hits[0].score == 1.0

    def test_requires_explicit_indexing_for_missing_collection(self, vector_store, client):
        with pytest.raises(IndexNotReadyError, match="Index is missing"):
            vector_store.search([1.0, 0.0], 5)

        assert not client.collection_exists("etch_user_guide_ru")

    def test_rejects_empty_collection(self, vector_store, client):
        client.create_collection(
            "etch_user_guide_ru",
            vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE),
        )

        with pytest.raises(IndexNotReadyError, match="Index is empty"):
            vector_store.search([1.0, 0.0], 5)

    def test_requires_reindexing_after_dimension_change(self, vector_store, chunk):
        vector_store.rebuild([chunk], [[1.0, 0.0]], 2)

        with pytest.raises(IndexNotReadyError, match="incompatible"):
            vector_store.search([1.0, 0.0, 0.0], 5)
