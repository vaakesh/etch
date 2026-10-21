from rag.errors import RagError


class Embedder:
    def __init__(self, model_name: str, device: str) -> None:
        """Load the cached embedding model on the requested device and detect its vector size."""
        from sentence_transformers import SentenceTransformer

        try:
            self._model = SentenceTransformer(model_name, device=device, local_files_only=True)
        except (OSError, ValueError, RuntimeError) as exc:
            raise RagError(f"Failed to load embedding model {model_name}: {exc}") from exc
        dimension = self._model.get_embedding_dimension()
        if dimension is None or dimension <= 0:
            raise RagError(f"Model {model_name} does not report a valid embedding dimension.")
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Encode document texts as normalized vectors for indexing."""
        try:
            return self._model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).tolist()
        except (ValueError, RuntimeError) as exc:
            raise RagError(f"Failed to compute embeddings: {exc}") from exc

    def embed_query(self, question: str) -> list[float]:
        """Encode a question in the same vector space as the document chunks."""
        return self.embed_documents([question])[0]
