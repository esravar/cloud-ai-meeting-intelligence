import uuid
from pathlib import Path

from app.celery_app import celery_app
from app.config import get_settings
from app.database import get_session_factory
from app.embeddings import OpenRouterEmbeddingProvider
from app.file_processing import OpenAITranscriber, extract_pdf_text
from app.models import ProcessingJob
from app.repository import JobRepository, MeetingRepository
from app.security import FieldCipher
from app.services import MeetingIngestionService


@celery_app.task(name="process_upload")
def process_upload(job_id: str) -> None:
    settings = get_settings()
    path: Path | None = None
    with get_session_factory()() as session:
        jobs = JobRepository(session)
        job = session.get(ProcessingJob, uuid.UUID(job_id))
        if not job:
            return
        path = Path(job.stored_path)
        jobs.set_status(job, "processing")
        try:
            if job.kind == "pdf":
                transcript = extract_pdf_text(path)
            elif job.kind == "audio":
                transcript = OpenAITranscriber(settings).transcribe(path)
            else:
                raise ValueError(f"Unsupported job kind: {job.kind}")

            repository = MeetingRepository(
                session, FieldCipher(settings.field_encryption_key)
            )
            result = MeetingIngestionService(
                repository,
                OpenRouterEmbeddingProvider(settings),
                settings,
            ).ingest(
                job.owner_id,
                job.title,
                transcript,
                source_type=job.kind,
                source_name=job.original_filename,
            )
            jobs.set_status(job, "completed", meeting_id=result.id)
        except Exception as exc:
            jobs.set_status(job, "failed", error=str(exc)[:1000])
            raise
        finally:
            path.unlink(missing_ok=True)
