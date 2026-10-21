from pathlib import Path

from rag.chunks import load_chunks
from rag.embedder import Embedder
from rag.llm import LLM
from rag.prompt import build_messages
from rag.reranker import Reranker
from rag.store import QdrantStore
from rag.types import Answer, RerankedHit


class RagService:
    def __init__(
        self,
        *,
        content_dir: Path,
        embedder: Embedder,
        store: QdrantStore,
        llm: LLM,
        reranker: Reranker,
        candidate_k: int,
        top_k: int,
    ) -> None:
        """Bind retrieval, reranking, and generation dependencies and validate their limits."""
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")
        if candidate_k < top_k:
            raise ValueError("candidate_k must be greater than or equal to top_k.")
        self._content_dir = content_dir
        self._embedder = embedder
        self._store = store
        self._llm = llm
        self._reranker = reranker
        self._candidate_k = candidate_k
        self._top_k = top_k

    def index(self) -> int:
        """Validate and embed the corpus, rebuild its collection, and return the chunk count."""
        chunks = load_chunks(self._content_dir)
        vectors = self._embedder.embed_documents([chunk.text for chunk in chunks])
        self._store.rebuild(chunks, vectors, self._embedder.dimension)
        return len(chunks)

    def search(self, question: str, *, k: int) -> list[RerankedHit]:
        """Retrieve a larger candidate pool and rerank it to k chunks without generation."""
        question = question.strip()
        if not question:
            raise ValueError("Question must not be empty.")
        if k <= 0:
            raise ValueError("k must be greater than zero.")
        vector = self._embedder.embed_query(question)
        candidates = self._store.search(vector, max(self._candidate_k, k))
        return self._reranker.rerank(question, candidates, k=k)

    def ask(self, question: str) -> Answer:
        """Retrieve context, build messages, and return an answer together with its sources."""
        question = question.strip()
        sources = self.search(question, k=self._top_k)
        if not sources:
            return Answer(text="В справке Etch не нашлось подходящих фрагментов.", sources=[])
        messages = build_messages(question, sources)
        return Answer(text=self._llm.generate(messages), sources=sources)
