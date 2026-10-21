class RagError(RuntimeError):
    """An actionable error during corpus preparation, retrieval, or generation."""


class CorpusError(RagError):
    """The source documents cannot be indexed."""


class IndexNotReadyError(RagError):
    """The collection needs to be indexed before searching."""
