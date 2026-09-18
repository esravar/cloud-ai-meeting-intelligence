import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.llm import LLMServiceError
from app.repository import RetrievedChunk
from app.services import MeetingIngestionService, RetrievalAnswerService
from tests.test_llm import make_settings


class FakeEmbeddings:
    model_name = "test-embeddings"
    dimensions = 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class FakeRepository:
    def __init__(self):
        self.created = None

    def create(
        self,
        owner_id,
        title,
        transcript,
        chunks,
        embeddings,
        embedding_model,
        embedding_dimensions,
        source_type,
        source_name,
    ):
        self.created = (title, transcript, chunks, embeddings)
        return SimpleNamespace(
            id=uuid.uuid4(),
            title=title,
            source_type=source_type,
            source_name=source_name,
            embedding_model=embedding_model,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def search(
        self,
        owner_id,
        query_embedding,
        embedding_model,
        embedding_dimensions,
        limit,
        meeting_id=None,
    ):
        meeting_uuid = meeting_id or uuid.uuid4()
        return [
            RetrievedChunk(
                chunk_id=uuid.uuid4(),
                meeting_id=meeting_uuid,
                meeting_title="Architecture Review",
                chunk_index=0,
                content="The team selected PostgreSQL with pgvector.",
                score=0.91,
            )
        ]


class FakeAnswerer:
    model_name = "test-model"

    def answer_question(self, question: str, contexts: list[str]) -> str:
        return "The team selected PostgreSQL with pgvector [1]."


class InvalidCitationAnswerer:
    model_name = "test-model"

    def answer_question(self, question: str, contexts: list[str]) -> str:
        return "The team selected PostgreSQL with pgvector [99]."


def test_ingestion_chunks_and_embeds_transcript() -> None:
    repository = FakeRepository()
    settings = make_settings()
    service = MeetingIngestionService(repository, FakeEmbeddings(), settings)

    result = service.ingest(
        uuid.uuid4(),
        "Architecture Review",
        " ".join(f"word-{index}" for index in range(230)),
    )

    assert result.chunk_count == 3
    assert len(repository.created[2]) == len(repository.created[3])


def test_answer_contains_retrieval_citations() -> None:
    repository = FakeRepository()
    service = RetrievalAnswerService(
        repository,
        FakeEmbeddings(),
        FakeAnswerer(),
        make_settings(),
    )

    result = service.answer(uuid.uuid4(), "Which database was selected?", None, 3)

    assert "[1]" in result.answer
    assert result.citations[0].meeting_title == "Architecture Review"
    assert result.citations[0].score == 0.91


def test_rejects_llm_answer_with_invalid_citation() -> None:
    service = RetrievalAnswerService(
        FakeRepository(),
        FakeEmbeddings(),
        InvalidCitationAnswerer(),
        make_settings(),
    )

    with pytest.raises(LLMServiceError, match="invalid citation"):
        service.answer(uuid.uuid4(), "Which database was selected?", None, 3)
