import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.config import Settings
from app.llm import LLMServiceError, OpenRouterMeetingSummarizer


def make_settings() -> Settings:
    return Settings(
        app_name="Test",
        app_version="0.1.0",
        environment="test",
        log_level="INFO",
        openrouter_api_key="test-key",
        openrouter_base_url="https://example.test/api/v1",
        openrouter_model="test-model",
        embedding_model="test-embedding-model",
        embedding_dimensions=1536,
        llm_timeout_seconds=1,
        database_url="postgresql+psycopg://test:test@localhost/test",
        chunk_size_words=100,
        chunk_overlap_words=20,
        retrieval_top_k=5,
        app_secret_key="test-secret",
        field_encryption_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        access_token_minutes=60,
        redis_url="redis://localhost:6379/0",
        upload_dir=Path("work/test-uploads"),
        max_upload_bytes=1024,
        openai_api_key=None,
        transcription_model="gpt-4o-mini-transcribe",
        otel_service_name="test",
        otel_exporter_otlp_endpoint=None,
        llm_input_cost_per_million=1.0,
        llm_output_cost_per_million=2.0,
        agent_history_turns=6,
    )


def test_parses_structured_model_response() -> None:
    service = OpenRouterMeetingSummarizer(make_settings())
    content = json.dumps(
        {
            "summary": "A short summary.",
            "decisions": ["Ship the feature."],
            "action_items": [
                {"description": "Write tests.", "owner": "Esra", "due_date": None}
            ],
            "risks": [],
        }
    )
    service._client = Mock()
    service._client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )

    result = service.summarize("A sufficiently long meeting transcript.")

    assert result.summary == "A short summary."
    assert result.action_items[0].owner == "Esra"


def test_rejects_invalid_model_response() -> None:
    service = OpenRouterMeetingSummarizer(make_settings())
    service._client = Mock()
    service._client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))]
    )

    with pytest.raises(LLMServiceError, match="invalid structured response"):
        service.summarize("A sufficiently long meeting transcript.")
