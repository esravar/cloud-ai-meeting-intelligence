import logging
from typing import Protocol

from openai import OpenAI

from app.config import Settings
from app.observability import observe_ai

logger = logging.getLogger(__name__)


class EmbeddingServiceError(RuntimeError):
    """Raised when embeddings cannot be generated."""


class EmbeddingProvider(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class UnconfiguredEmbeddingProvider:
    model_name = "unconfigured"
    dimensions = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingServiceError("OPENROUTER_API_KEY is not configured.")

    def embed_query(self, text: str) -> list[float]:
        raise EmbeddingServiceError("OPENROUTER_API_KEY is not configured.")


class OpenRouterEmbeddingProvider:
    def __init__(self, settings: Settings):
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured.")

        self.model_name = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self._settings = settings
        self._client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            with observe_ai("embedding", self.model_name) as observed:
                response = self._client.embeddings.create(
                    model=self.model_name,
                    input=texts,
                    dimensions=self.dimensions,
                )
                usage = getattr(response, "usage", None)
                observed["input_tokens"] = (
                    int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
                )
            ordered = sorted(response.data, key=lambda item: item.index)
            embeddings = [item.embedding for item in ordered]
            if len(embeddings) != len(texts):
                raise EmbeddingServiceError(
                    "Embedding provider returned an unexpected number of vectors."
                )
            return embeddings
        except EmbeddingServiceError:
            raise
        except Exception as exc:
            logger.exception("Embedding request failed.")
            raise EmbeddingServiceError("The embedding request failed.") from exc

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
