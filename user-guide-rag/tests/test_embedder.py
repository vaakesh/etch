from unittest.mock import Mock

import pytest

from rag.embedder import Embedder
from rag.errors import RagError


@pytest.fixture
def model_factory(monkeypatch):
    model = Mock()
    model.get_embedding_dimension.return_value = 1024
    factory = Mock(return_value=model)
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", factory)
    return factory


class TestEmbedder:
    def test_loads_model_from_local_files_with_configured_device(self, model_factory):
        embedder = Embedder(model_name="BAAI/bge-m3", device="cpu")

        assert embedder.dimension == 1024
        model_factory.assert_called_once_with("BAAI/bge-m3", device="cpu", local_files_only=True)

    def test_reports_missing_cached_weights_without_retrying_download(self, model_factory):
        model_factory.side_effect = OSError("Weights are missing from the cache.")

        with pytest.raises(RagError, match="Failed to load embedding model.*Weights are missing"):
            Embedder(model_name="BAAI/bge-m3", device="cpu")

        model_factory.assert_called_once_with("BAAI/bge-m3", device="cpu", local_files_only=True)
