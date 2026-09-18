from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.llm import LLMServiceError
from app.main import (
    app,
    get_current_user,
    get_ingestion_service,
    get_job_repository,
    get_retrieval_service,
    get_summarizer,
)
from app.schemas import (
    ActionItem,
    AnswerResponse,
    Citation,
    MeetingListResponse,
    MeetingResponse,
    MeetingSummary,
)


@pytest.fixture(autouse=True)
def authenticated_user():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="7d2cc622-887a-49a2-a381-b8cbf6279136"
    )
    yield
    app.dependency_overrides.clear()


class FakeSummarizer:
    model_name = "test-model"

    def summarize(self, text: str) -> MeetingSummary:
        return MeetingSummary(
            summary="The team approved the production rollout.",
            decisions=["Release the API on Friday."],
            action_items=[
                ActionItem(
                    description="Prepare the release checklist.",
                    owner="Esra",
                    due_date="Friday",
                )
            ],
            risks=["The monitoring dashboard is not ready."],
        )


class FailingSummarizer:
    model_name = "test-model"

    def summarize(self, text: str) -> MeetingSummary:
        raise LLMServiceError("Upstream model unavailable.")


class FakeIngestionService:
    meeting_id = "7d2cc622-887a-49a2-a381-b8cbf6279136"

    def ingest(self, owner_id, title: str, transcript: str) -> MeetingResponse:
        return MeetingResponse(
            id=self.meeting_id,
            title=title,
            chunk_count=2,
            source_type="text",
            source_name=None,
            embedding_model="test-embedding",
            created_at="2026-07-27T10:00:00Z",
            updated_at="2026-07-27T10:00:00Z",
        )

    def get(self, meeting_id, owner_id) -> MeetingResponse:
        return MeetingResponse(
            id=meeting_id,
            title="Architecture Review",
            chunk_count=2,
            source_type="text",
            source_name=None,
            embedding_model="test-embedding",
            created_at="2026-07-27T10:00:00Z",
            updated_at="2026-07-27T10:00:00Z",
        )

    def list_for_owner(self, owner_id, limit: int, offset: int) -> MeetingListResponse:
        return MeetingListResponse(
            items=[self.get(self.meeting_id, owner_id)],
            total=1,
            limit=limit,
            offset=offset,
        )


class FakeJobRepository:
    job = SimpleNamespace(
        id="001f63a9-6ca7-45d5-845c-2ec6f6bf30df",
        kind="pdf",
        status="completed",
        original_filename="meeting.pdf",
        title="Architecture Review",
        meeting_id="7d2cc622-887a-49a2-a381-b8cbf6279136",
        error=None,
        created_at="2026-07-27T10:00:00Z",
        updated_at="2026-07-27T10:01:00Z",
    )

    def list_for_owner(self, owner_id, limit, offset):
        return [self.job], 1

    def get(self, job_id, owner_id):
        return self.job


class FakeRetrievalService:
    def answer(self, owner_id, question, meeting_id, top_k) -> AnswerResponse:
        return AnswerResponse(
            answer="PostgreSQL with pgvector was selected [1].",
            citations=[
                Citation(
                    index=1,
                    meeting_id="7d2cc622-887a-49a2-a381-b8cbf6279136",
                    meeting_title="Architecture Review",
                    chunk_id="21630e91-4f18-469c-a97a-796824bbca5a",
                    chunk_index=0,
                    score=0.93,
                    excerpt="The team selected PostgreSQL with pgvector.",
                )
            ],
            model="test-model",
        )


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.0"}


def test_create_structured_summary() -> None:
    app.dependency_overrides[get_summarizer] = lambda: FakeSummarizer()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/summaries",
                json={
                    "text": (
                        "The team approved the release. Esra will prepare the "
                        "checklist before Friday."
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "test-model"
    assert payload["result"]["decisions"] == ["Release the API on Friday."]
    assert payload["result"]["action_items"][0]["owner"] == "Esra"


def test_rejects_short_transcript() -> None:
    with TestClient(app) as client:
        response = client.post("/summaries", json={"text": "Too short"})

    assert response.status_code == 422


def test_returns_bad_gateway_for_llm_failure() -> None:
    app.dependency_overrides[get_summarizer] = lambda: FailingSummarizer()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/summaries",
                json={"text": "This is a sufficiently long meeting transcript."},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "Upstream model unavailable."}


def test_ingests_meeting() -> None:
    app.dependency_overrides[get_ingestion_service] = lambda: FakeIngestionService()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="7d2cc622-887a-49a2-a381-b8cbf6279136"
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/meetings",
                json={
                    "title": "Architecture Review",
                    "transcript": (
                        "The team reviewed storage options and selected "
                        "PostgreSQL with pgvector."
                    ),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["chunk_count"] == 2


def test_lists_meetings_with_pagination() -> None:
    app.dependency_overrides[get_ingestion_service] = lambda: FakeIngestionService()
    try:
        with TestClient(app) as client:
            response = client.get("/meetings?limit=10&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "Architecture Review"


def test_lists_jobs_with_pagination() -> None:
    app.dependency_overrides[get_job_repository] = lambda: FakeJobRepository()
    try:
        with TestClient(app) as client:
            response = client.get("/jobs?limit=10&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["status"] == "completed"


def test_answers_with_citations() -> None:
    app.dependency_overrides[get_retrieval_service] = lambda: FakeRetrievalService()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="7d2cc622-887a-49a2-a381-b8cbf6279136"
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/questions",
                json={"question": "Which database was selected?", "top_k": 3},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["citations"][0]["score"] == 0.93
