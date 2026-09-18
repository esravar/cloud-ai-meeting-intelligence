import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AgentThread,
    AgentTurn,
    Meeting,
    MeetingChunk,
    ProcessingJob,
    User,
)
from app.observability import Usage
from app.security import FieldCipher


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    meeting_id: uuid.UUID
    meeting_title: str
    chunk_index: int
    content: str
    score: float


class TransactionalRepository:
    def __init__(self, session: Session):
        self._session = session

    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise


class UserRepository(TransactionalRepository):
    def create(self, email: str, password_hash: str) -> User:
        user = User(email=email.lower(), password_hash=password_hash)
        self._session.add(user)
        self._commit()
        self._session.refresh(user)
        return user

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email.lower()))

    def get(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)


class MeetingRepository(TransactionalRepository):
    def __init__(self, session: Session, cipher: FieldCipher):
        super().__init__(session)
        self._cipher = cipher

    def create(
        self,
        owner_id: uuid.UUID,
        title: str,
        transcript: str,
        chunks: list[str],
        embeddings: list[list[float]],
        embedding_model: str,
        embedding_dimensions: int,
        source_type: str = "text",
        source_name: str | None = None,
    ) -> Meeting:
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have one embedding.")

        meeting = Meeting(
            owner_id=owner_id,
            title=title,
            transcript_encrypted=self._cipher.encrypt(transcript),
            source_type=source_type,
            source_name=source_name,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
        )
        meeting.chunks = [
            MeetingChunk(
                chunk_index=index,
                content_encrypted=self._cipher.encrypt(content),
                embedding=embedding,
            )
            for index, (content, embedding) in enumerate(zip(chunks, embeddings))
        ]
        self._session.add(meeting)
        self._commit()
        self._session.refresh(meeting)
        return meeting

    def get(self, meeting_id: uuid.UUID, owner_id: uuid.UUID) -> Meeting | None:
        statement = (
            select(Meeting)
            .options(selectinload(Meeting.chunks))
            .where(Meeting.id == meeting_id, Meeting.owner_id == owner_id)
        )
        return self._session.scalar(statement)

    def list_for_owner(
        self, owner_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[Meeting], int]:
        total = (
            self._session.scalar(
                select(func.count(Meeting.id)).where(Meeting.owner_id == owner_id)
            )
            or 0
        )
        meetings = list(
            self._session.scalars(
                select(Meeting)
                .options(selectinload(Meeting.chunks))
                .where(Meeting.owner_id == owner_id)
                .order_by(Meeting.created_at.desc(), Meeting.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return meetings, total

    def update(
        self,
        meeting: Meeting,
        title: str,
        transcript: str,
        chunks: list[str],
        embeddings: list[list[float]],
        embedding_model: str,
        embedding_dimensions: int,
    ) -> Meeting:
        meeting.title = title
        meeting.transcript_encrypted = self._cipher.encrypt(transcript)
        meeting.embedding_model = embedding_model
        meeting.embedding_dimensions = embedding_dimensions
        meeting.chunks = [
            MeetingChunk(
                chunk_index=index,
                content_encrypted=self._cipher.encrypt(content),
                embedding=embedding,
            )
            for index, (content, embedding) in enumerate(zip(chunks, embeddings))
        ]
        self._commit()
        self._session.refresh(meeting)
        return meeting

    def delete(self, meeting: Meeting) -> None:
        self._session.delete(meeting)
        self._commit()

    def transcript(self, meeting: Meeting) -> str:
        return self._cipher.decrypt(meeting.transcript_encrypted)

    def search(
        self,
        owner_id: uuid.UUID,
        query_embedding: list[float],
        embedding_model: str,
        embedding_dimensions: int,
        limit: int,
        meeting_id: uuid.UUID | None = None,
    ) -> list[RetrievedChunk]:
        distance = MeetingChunk.embedding.cosine_distance(query_embedding)
        statement = (
            select(MeetingChunk, Meeting.title, distance.label("distance"))
            .join(Meeting, Meeting.id == MeetingChunk.meeting_id)
            .where(
                Meeting.owner_id == owner_id,
                Meeting.embedding_model == embedding_model,
                Meeting.embedding_dimensions == embedding_dimensions,
            )
            .order_by(distance)
            .limit(limit)
        )
        if meeting_id:
            statement = statement.where(MeetingChunk.meeting_id == meeting_id)

        results = self._session.execute(statement).all()
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                meeting_id=chunk.meeting_id,
                meeting_title=title,
                chunk_index=chunk.chunk_index,
                content=self._cipher.decrypt(chunk.content_encrypted),
                score=max(0.0, 1.0 - float(raw_distance)),
            )
            for chunk, title, raw_distance in results
        ]

    def stale_meeting_ids(
        self,
        owner_id: uuid.UUID,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> list[uuid.UUID]:
        return list(
            self._session.scalars(
                select(Meeting.id).where(
                    Meeting.owner_id == owner_id,
                    (Meeting.embedding_model != embedding_model)
                    | (Meeting.embedding_dimensions != embedding_dimensions),
                )
            )
        )


class JobRepository(TransactionalRepository):
    def create(
        self,
        owner_id: uuid.UUID,
        kind: str,
        original_filename: str,
        stored_path: str,
        title: str,
        file_size: int,
    ) -> ProcessingJob:
        job = ProcessingJob(
            owner_id=owner_id,
            kind=kind,
            original_filename=original_filename,
            stored_path=stored_path,
            title=title,
            file_size=file_size,
        )
        self._session.add(job)
        self._commit()
        self._session.refresh(job)
        return job

    def get(self, job_id: uuid.UUID, owner_id: uuid.UUID) -> ProcessingJob | None:
        return self._session.scalar(
            select(ProcessingJob).where(
                ProcessingJob.id == job_id,
                ProcessingJob.owner_id == owner_id,
            )
        )

    def list_for_owner(
        self, owner_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[ProcessingJob], int]:
        total = (
            self._session.scalar(
                select(func.count(ProcessingJob.id)).where(
                    ProcessingJob.owner_id == owner_id
                )
            )
            or 0
        )
        jobs = list(
            self._session.scalars(
                select(ProcessingJob)
                .where(ProcessingJob.owner_id == owner_id)
                .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return jobs, total

    def set_status(
        self,
        job: ProcessingJob,
        status: str,
        meeting_id: uuid.UUID | None = None,
        error: str | None = None,
    ) -> None:
        job.status = status
        job.meeting_id = meeting_id
        job.error = error
        self._commit()

    def delete_file_record(self, job_id: uuid.UUID) -> None:
        self._session.execute(delete(ProcessingJob).where(ProcessingJob.id == job_id))
        self._commit()


class AgentRepository(TransactionalRepository):
    def __init__(self, session: Session, cipher: FieldCipher):
        super().__init__(session)
        self._cipher = cipher

    def create_thread(
        self, owner_id: uuid.UUID, title: str, meeting_id: uuid.UUID | None
    ) -> AgentThread:
        thread = AgentThread(owner_id=owner_id, title=title, meeting_id=meeting_id)
        self._session.add(thread)
        self._commit()
        self._session.refresh(thread)
        return thread

    def get_thread(
        self, thread_id: uuid.UUID, owner_id: uuid.UUID
    ) -> AgentThread | None:
        return self._session.scalar(
            select(AgentThread)
            .options(selectinload(AgentThread.turns))
            .where(
                AgentThread.id == thread_id,
                AgentThread.owner_id == owner_id,
            )
        )

    def add_turn(
        self,
        thread: AgentThread,
        role: str,
        content: str,
        state: str,
        trace_id: str | None = None,
        usage: Usage | None = None,
    ) -> AgentTurn:
        usage = usage or Usage()
        turn = AgentTurn(
            thread=thread,
            role=role,
            content_encrypted=self._cipher.encrypt(content),
            state=state,
            trace_id=trace_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=f"{usage.estimated_cost_usd:.8f}",
        )
        thread.state = state
        self._session.add(turn)
        self._commit()
        self._session.refresh(turn)
        return turn

    def set_state(self, thread: AgentThread, state: str, status: str = "ready") -> None:
        thread.state = state
        thread.status = status
        self._commit()

    def history(self, thread: AgentThread, limit: int) -> list[tuple[str, str]]:
        return [
            (turn.role, self._cipher.decrypt(turn.content_encrypted))
            for turn in thread.turns[-limit:]
        ]

    def turn_content(self, turn: AgentTurn) -> str:
        return self._cipher.decrypt(turn.content_encrypted)
