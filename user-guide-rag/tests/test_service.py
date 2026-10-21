from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from rag.errors import CorpusError, IndexNotReadyError, RagError
from rag.service import RagService
from rag.types import Answer, ChatMessage


class TestAsk:
    def test_returns_answer_and_sends_reranked_context_to_llm(
        self, service, hit, reranked_hit, store, reranker, llm
    ):
        result = service.ask("Как создать карточку?")

        assert result == Answer(text="Нажмите «Новая карточка».", sources=[reranked_hit])
        store.search.assert_called_once_with([1.0, 0.0], 20)
        reranker.rerank.assert_called_once_with("Как создать карточку?", [hit], k=5)
        llm.generate.assert_called_once()
        messages = llm.generate.call_args.args[0]
        assert messages[0]["role"] == "system"
        assert messages[1] == {
            "role": "user",
            "content": (
                "Фрагменты справки:\n<context>\n"
                "[1] content/ru/05-cards.md (etch.cards.create)\n"
                "# Etch: как создать карточку\n\nНажмите «Новая карточка»."
                "\n</context>\n\nВопрос: Как создать карточку?"
            ),
        }

    def test_accepts_another_provider_without_inheritance(
        self, embedder, store, reranker, reranked_hit
    ):
        class OtherLLM:
            def generate(self, messages: list[ChatMessage]) -> str:
                return "Ответ другого провайдера."

        service = RagService(
            content_dir=Path("/guide/content/ru"),
            embedder=embedder,
            store=store,
            llm=OtherLLM(),
            reranker=reranker,
            candidate_k=20,
            top_k=2,
        )

        result = service.ask("Как создать карточку?")

        assert result == Answer(text="Ответ другого провайдера.", sources=[reranked_hit])

    def test_preserves_reranker_order_in_sources_and_prompt(
        self, service, hit, reranked_hit, store, reranker, llm
    ):
        other = replace(
            reranked_hit,
            chunk_id="etch.cards.assign",
            text="# Назначение колоды\n\nВыберите колоду.",
            rerank_score=8.0,
        )
        store.search.return_value = [hit, other]
        reranker.rerank.return_value = [other, reranked_hit]

        result = service.ask("Как создать карточку?")

        assert result.sources == [other, reranked_hit]
        context = llm.generate.call_args.args[0][1]["content"]
        assert context.index("etch.cards.assign") < context.index("etch.cards.create")

    def test_does_not_generate_when_retrieval_fails(self, service, store, llm):
        store.search.side_effect = IndexNotReadyError("Index is missing.")

        with pytest.raises(IndexNotReadyError, match="Index is missing"):
            service.ask("Как создать карточку?")

        llm.generate.assert_not_called()

    def test_does_not_generate_when_reranking_fails(self, service, reranker, llm):
        reranker.rerank.side_effect = RagError("Reranking model failed.")

        with pytest.raises(RagError, match="Reranking model failed"):
            service.ask("Как создать карточку?")

        llm.generate.assert_not_called()

    def test_does_not_generate_when_no_fragments_are_found(self, service, store, reranker, llm):
        store.search.return_value = []
        reranker.rerank.return_value = []

        result = service.ask("Как создать карточку?")

        assert result == Answer(text="В справке Etch не нашлось подходящих фрагментов.", sources=[])
        llm.generate.assert_not_called()

    def test_propagates_generation_failure(self, service, llm):
        llm.generate.side_effect = RagError("Generation is unavailable.")

        with pytest.raises(RagError, match="Generation is unavailable"):
            service.ask("Как создать карточку?")


class TestSearch:
    def test_normalizes_question_and_respects_result_limit(
        self, service, embedder, store, reranker, hit, reranked_hit, llm
    ):
        result = service.search("  Как создать карточку? \n", k=3)

        assert result == [reranked_hit]
        embedder.embed_query.assert_called_once_with("Как создать карточку?")
        store.search.assert_called_once_with([1.0, 0.0], 20)
        reranker.rerank.assert_called_once_with("Как создать карточку?", [hit], k=3)
        llm.generate.assert_not_called()

    def test_expands_candidate_pool_when_requested_limit_exceeds_configuration(
        self, service, store, reranker, hit
    ):
        service.search("Как создать карточку?", k=25)

        store.search.assert_called_once_with([1.0, 0.0], 25)
        reranker.rerank.assert_called_once_with("Как создать карточку?", [hit], k=25)

    @pytest.mark.parametrize("question", ["", " \t\n"])
    def test_rejects_blank_question_before_calling_dependencies(
        self, service, embedder, store, llm, question
    ):
        with pytest.raises(ValueError, match="Question must not be empty"):
            service.ask(question)

        embedder.embed_query.assert_not_called()
        store.search.assert_not_called()
        llm.generate.assert_not_called()

    @pytest.mark.parametrize("k", [0, -1])
    def test_rejects_nonpositive_limit(self, service, embedder, k):
        with pytest.raises(ValueError, match="k must be greater than zero"):
            service.search("Как создать карточку?", k=k)

        embedder.embed_query.assert_not_called()


class TestIndex:
    def test_indexes_without_reranking(self, service, chunk, embedder, store, reranker, llm):
        with patch("rag.service.load_chunks", return_value=[chunk]) as load:
            result = service.index()

        assert result == 1
        load.assert_called_once_with(Path("/guide/content/ru"))
        embedder.embed_documents.assert_called_once_with([chunk.text])
        store.rebuild.assert_called_once_with([chunk], [[1.0, 0.0]], 2)
        reranker.rerank.assert_not_called()
        llm.generate.assert_not_called()

    def test_preserves_index_when_corpus_validation_fails(self, service, embedder, store):
        with patch("rag.service.load_chunks", side_effect=CorpusError("Duplicate chunk_id.")):
            with pytest.raises(CorpusError, match="Duplicate chunk_id"):
                service.index()

        embedder.embed_documents.assert_not_called()
        store.rebuild.assert_not_called()

    def test_preserves_index_when_embedding_fails(self, service, chunk, embedder, store):
        embedder.embed_documents.side_effect = RagError("Embedding model failed.")

        with patch("rag.service.load_chunks", return_value=[chunk]):
            with pytest.raises(RagError, match="Embedding model failed"):
                service.index()

        store.rebuild.assert_not_called()


class TestRagService:
    @pytest.mark.parametrize("top_k", [0, -1])
    def test_rejects_nonpositive_configured_limit(self, embedder, store, llm, reranker, top_k):
        with pytest.raises(ValueError, match="top_k must be greater than zero"):
            RagService(
                content_dir=Path("/guide/content/ru"),
                embedder=embedder,
                store=store,
                llm=llm,
                reranker=reranker,
                candidate_k=20,
                top_k=top_k,
            )

    @pytest.mark.parametrize("candidate_k", [-1, 0, 4])
    def test_rejects_candidate_pool_smaller_than_top_k(
        self, embedder, store, llm, reranker, candidate_k
    ):
        with pytest.raises(ValueError, match="candidate_k must be greater than or equal to top_k"):
            RagService(
                content_dir=Path("/guide/content/ru"),
                embedder=embedder,
                store=store,
                llm=llm,
                reranker=reranker,
                candidate_k=candidate_k,
                top_k=5,
            )
