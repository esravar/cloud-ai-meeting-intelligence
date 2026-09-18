from types import SimpleNamespace
from unittest.mock import Mock

from app.embeddings import OpenRouterEmbeddingProvider
from tests.test_llm import make_settings


def test_preserves_embedding_input_order() -> None:
    provider = OpenRouterEmbeddingProvider(make_settings())
    provider._client = Mock()
    provider._client.embeddings.create.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=[0.0, 1.0]),
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
        ]
    )

    vectors = provider.embed_documents(["first", "second"])

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
