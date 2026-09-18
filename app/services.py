import re
import uuid

from app.chunking import chunk_text
from app.config import Settings
from app.embeddings import EmbeddingProvider
from app.llm import LLMServiceError, MeetingSummarizer
from app.repository import MeetingRepository
from app.schemas import AnswerResponse, Citation, MeetingListResponse, MeetingResponse


class MeetingNotFoundError(RuntimeError):
    pass


class NoSearchResultsError(RuntimeError):
    pass


class MeetingIngestionService:
    def __init__(
        self,
        repository: MeetingRepository,
        embeddings: EmbeddingProvider,
        settings: Settings,
    ):
        self._repository = repository
        self._embeddings = embeddings
        self._settings = settings

    def ingest(
        self,
        owner_id: uuid.UUID,
        title: str,
        transcript: str,
        source_type: str = "text",
        source_name: str | None = None,
    ) -> MeetingResponse:
        chunks = self._chunks(transcript)
        vectors = self._embeddings.embed_documents(chunks)
        meeting = self._repository.create(
            owner_id,
            title,
            transcript,
            chunks,
            vectors,
            self._embeddings.model_name,
            self._embeddings.dimensions,
            source_type,
            source_name,
        )
        return self._response(meeting, len(chunks))

    def get(self, meeting_id: uuid.UUID, owner_id: uuid.UUID) -> MeetingResponse:
        meeting = self._require(meeting_id, owner_id)
        return self._response(meeting, len(meeting.chunks))

    def list_for_owner(
        self, owner_id: uuid.UUID, limit: int, offset: int
    ) -> MeetingListResponse:
        meetings, total = self._repository.list_for_owner(owner_id, limit, offset)
        return MeetingListResponse(
            items=[self._response(item, len(item.chunks)) for item in meetings],
            total=total,
            limit=limit,
            offset=offset,
        )

    def update(
        self,
        meeting_id: uuid.UUID,
        owner_id: uuid.UUID,
        title: str | None,
        transcript: str | None,
    ) -> MeetingResponse:
        meeting = self._require(meeting_id, owner_id)
        new_title = title or meeting.title
        new_transcript = transcript or self._repository.transcript(meeting)
        chunks = self._chunks(new_transcript)
        vectors = self._embeddings.embed_documents(chunks)
        updated = self._repository.update(
            meeting,
            new_title,
            new_transcript,
            chunks,
            vectors,
            self._embeddings.model_name,
            self._embeddings.dimensions,
        )
        return self._response(updated, len(chunks))

    def delete(self, meeting_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        self._repository.delete(self._require(meeting_id, owner_id))

    def reindex(self, meeting_id: uuid.UUID, owner_id: uuid.UUID) -> MeetingResponse:
        return self.update(meeting_id, owner_id, None, None)

    def _require(self, meeting_id: uuid.UUID, owner_id: uuid.UUID):
        meeting = self._repository.get(meeting_id, owner_id)
        if not meeting:
            raise MeetingNotFoundError(f"Meeting {meeting_id} was not found.")
        return meeting

    def _chunks(self, transcript: str) -> list[str]:
        return chunk_text(
            transcript,
            self._settings.chunk_size_words,
            self._settings.chunk_overlap_words,
        )

    @staticmethod
    def _response(meeting, chunk_count: int) -> MeetingResponse:
        return MeetingResponse(
            id=meeting.id,
            title=meeting.title,
            chunk_count=chunk_count,
            source_type=meeting.source_type,
            source_name=meeting.source_name,
            embedding_model=meeting.embedding_model,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
        )


class RetrievalAnswerService:
    def __init__(
        self,
        repository: MeetingRepository,
        embeddings: EmbeddingProvider,
        summarizer: MeetingSummarizer,
        settings: Settings,
    ):
        self._repository = repository
        self._embeddings = embeddings
        self._summarizer = summarizer
        self._settings = settings

    def answer(
        self,
        owner_id: uuid.UUID,
        question: str,
        meeting_id: uuid.UUID | None,
        top_k: int | None,
    ) -> AnswerResponse:
        query_vector = self._embeddings.embed_query(question)
        chunks = self._repository.search(
            owner_id,
            query_vector,
            self._embeddings.model_name,
            self._embeddings.dimensions,
            top_k or self._settings.retrieval_top_k,
            meeting_id,
        )
        if not chunks:
            raise NoSearchResultsError(
                "No compatible meeting excerpts were found. Reindex stale meetings."
            )

        answer = self._summarizer.answer_question(
            question, [chunk.content for chunk in chunks]
        )
        references = {int(value) for value in re.findall(r"\[(\d+)]", answer)}
        valid = {index for index in references if 1 <= index <= len(chunks)}
        if not valid:
            raise LLMServiceError(
                "The language model answer contained an invalid citation."
            )
        if valid != references:
            raise LLMServiceError(
                "The language model answer contained an invalid citation."
            )

        citations = [
            Citation(
                index=index,
                meeting_id=chunk.meeting_id,
                meeting_title=chunk.meeting_title,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                score=round(chunk.score, 4),
                excerpt=chunk.content[:500],
            )
            for index, chunk in enumerate(chunks, start=1)
            if index in valid
        ]
        return AnswerResponse(
            answer=answer,
            citations=citations,
            model=self._summarizer.model_name,
        )
