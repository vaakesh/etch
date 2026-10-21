from dataclasses import replace
from unittest.mock import Mock

import pytest
from torch.nn import Identity

from rag.errors import RagError
from rag.reranker import Reranker
from rag.types import RerankedHit


@pytest.fixture
def model_factory(monkeypatch):
    model = Mock()
    model.predict.return_value = [4.5]
    factory = Mock(return_value=model)
    monkeypatch.setattr("sentence_transformers.CrossEncoder", factory)
    return factory


@pytest.fixture
def reranker():
    return Reranker(
        model_name="BAAI/bge-reranker-v2-m3",
        device="cpu",
        dtype="float32",
        batch_size=8,
        max_length=1024,
    )


class TestRerank:
    def test_scores_pairs_and_preserves_metadata_and_cosine(self, reranker, model_factory, hit):
        second = replace(
            hit,
            chunk_id="etch.cards.assign",
            title="Назначение колоды",
            text="# Назначение колоды\n\nВыберите колоду.",
            score=0.7,
        )
        model_factory.return_value.predict.return_value = [-2.0, 8.0]

        results = reranker.rerank("  Как выбрать колоду? \n", [hit, second], k=1)

        assert results == [
            RerankedHit(
                chunk_id="etch.cards.assign",
                title="Назначение колоды",
                text="# Назначение колоды\n\nВыберите колоду.",
                source="content/ru/05-cards.md",
                score=0.7,
                rerank_score=8.0,
            )
        ]
        assert hit.score == 0.9
        model_factory.return_value.predict.assert_called_once_with(
            [
                ("Как выбрать колоду?", hit.text),
                ("Как выбрать колоду?", second.text),
            ],
            batch_size=8,
            show_progress_bar=False,
        )

    def test_preserves_original_order_for_equal_scores(self, reranker, model_factory, hit):
        second = replace(hit, chunk_id="etch.cards.assign")
        model_factory.return_value.predict.return_value = [2.0, 2.0]

        results = reranker.rerank("Как создать карточку?", [hit, second], k=5)

        assert [result.chunk_id for result in results] == ["etch.cards.create", "etch.cards.assign"]

    def test_returns_available_candidates_with_raw_negative_scores(
        self, reranker, model_factory, hit, reranked_hit
    ):
        model_factory.return_value.predict.return_value = [-7.25]

        results = reranker.rerank("Как создать карточку?", [hit], k=5)

        assert results == [replace(reranked_hit, rerank_score=-7.25)]

    def test_returns_empty_list_without_loading_model(self, reranker, model_factory):
        results = reranker.rerank("Как создать карточку?", [], k=5)

        assert results == []
        model_factory.assert_not_called()

    @pytest.mark.parametrize("question", ["", " \t\n"])
    def test_rejects_blank_question_before_loading_model(
        self, reranker, model_factory, hit, question
    ):
        with pytest.raises(ValueError, match="Question must not be empty"):
            reranker.rerank(question, [hit], k=5)

        model_factory.assert_not_called()

    @pytest.mark.parametrize("k", [0, -1])
    def test_rejects_nonpositive_limit_before_loading_model(self, reranker, model_factory, hit, k):
        with pytest.raises(ValueError, match="k must be greater than zero"):
            reranker.rerank("Как создать карточку?", [hit], k=k)

        model_factory.assert_not_called()

    def test_loads_model_once_with_explicit_cpu_settings(self, reranker, model_factory, hit):
        model_factory.assert_not_called()

        reranker.rerank("Как создать карточку?", [hit], k=5)
        reranker.rerank("Как добавить карточку?", [hit], k=3)

        model_factory.assert_called_once()
        assert model_factory.call_args.args == ("BAAI/bge-reranker-v2-m3",)
        settings = model_factory.call_args.kwargs
        assert settings["device"] == "cpu"
        assert settings["local_files_only"] is True
        assert settings["model_kwargs"] == {"dtype": "float32"}
        assert settings["max_length"] == 1024
        assert isinstance(settings["activation_fn"], Identity)

    def test_wraps_model_loading_failure(self, reranker, model_factory, hit):
        model_factory.side_effect = OSError("Weights are missing.")

        with pytest.raises(RagError, match="Failed to load reranking model.*Weights are missing"):
            reranker.rerank("Как создать карточку?", [hit], k=5)

    def test_wraps_prediction_failure(self, reranker, model_factory, hit):
        model_factory.return_value.predict.side_effect = RuntimeError("Out of memory.")

        with pytest.raises(RagError, match="Failed to rerank fragments: Out of memory"):
            reranker.rerank("Как создать карточку?", [hit], k=5)

    @pytest.mark.parametrize("scores", [[], [1.0, 2.0], [float("nan")], [float("inf")]])
    def test_rejects_missing_or_nonfinite_model_scores(self, reranker, model_factory, hit, scores):
        model_factory.return_value.predict.return_value = scores

        with pytest.raises(RagError, match="one finite score per candidate"):
            reranker.rerank("Как создать карточку?", [hit], k=5)


class TestReranker:
    @pytest.mark.parametrize(
        ("batch_size", "max_length", "message"),
        [(0, 1024, "batch_size"), (-1, 1024, "batch_size"), (8, 0, "max_length")],
    )
    def test_rejects_nonpositive_model_limits(self, batch_size, max_length, message):
        with pytest.raises(ValueError, match=f"{message} must be greater than zero"):
            Reranker(
                model_name="BAAI/bge-reranker-v2-m3",
                device="cpu",
                dtype="float32",
                batch_size=batch_size,
                max_length=max_length,
            )
