import os
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    log_level: str
    openrouter_api_key: str | None
    openrouter_base_url: str
    openrouter_model: str
    embedding_model: str
    embedding_dimensions: int
    llm_timeout_seconds: float
    database_url: str
    chunk_size_words: int
    chunk_overlap_words: int
    retrieval_top_k: int
    app_secret_key: str
    field_encryption_key: str
    access_token_minutes: int
    redis_url: str
    upload_dir: Path
    max_upload_bytes: int
    openai_api_key: str | None
    transcription_model: str
    otel_service_name: str
    otel_exporter_otlp_endpoint: str | None
    llm_input_cost_per_million: float
    llm_output_cost_per_million: float
    agent_history_turns: int

    def validate_for_runtime(self) -> None:
        if self.environment != "production":
            return
        if self.app_secret_key in {"development-only-change-me", ""}:
            raise RuntimeError("APP_SECRET_KEY must be set in production.")
        if not os.getenv("FIELD_ENCRYPTION_KEY"):
            raise RuntimeError("FIELD_ENCRYPTION_KEY must be set in production.")
        if "meeting:meeting@" in self.database_url:
            raise RuntimeError("Development database credentials are forbidden.")


@lru_cache
def get_settings() -> Settings:
    app_secret = os.getenv("APP_SECRET_KEY", "development-only-change-me")
    development_encryption_key = urlsafe_b64encode(
        sha256(f"{app_secret}:field-encryption".encode()).digest()
    ).decode()
    settings = Settings(
        app_name=os.getenv("APP_NAME", "Cloud AI Meeting Intelligence"),
        app_version=os.getenv("APP_VERSION", "0.2.0"),
        environment=os.getenv("ENVIRONMENT", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
        openrouter_model=os.getenv(
            "OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free"
        ),
        embedding_model=os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small"),
        embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://meeting:meeting@localhost:5432/meeting_intelligence",
        ),
        chunk_size_words=int(os.getenv("CHUNK_SIZE_WORDS", "180")),
        chunk_overlap_words=int(os.getenv("CHUNK_OVERLAP_WORDS", "30")),
        retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "5")),
        app_secret_key=app_secret,
        field_encryption_key=os.getenv(
            "FIELD_ENCRYPTION_KEY", development_encryption_key
        ),
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "60")),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        upload_dir=Path(os.getenv("UPLOAD_DIR", "work/uploads")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", "26214400")),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        transcription_model=os.getenv("TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"),
        otel_service_name=os.getenv("OTEL_SERVICE_NAME", "meeting-intelligence-api"),
        otel_exporter_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        llm_input_cost_per_million=float(os.getenv("LLM_INPUT_COST_PER_MILLION", "0")),
        llm_output_cost_per_million=float(
            os.getenv("LLM_OUTPUT_COST_PER_MILLION", "0")
        ),
        agent_history_turns=int(os.getenv("AGENT_HISTORY_TURNS", "6")),
    )
    settings.validate_for_runtime()
    return settings
