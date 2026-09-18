import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.agent import StatefulAgentWorkflow
from app.auth import AuthService, UserAlreadyExistsError
from app.celery_app import celery_app
from app.config import get_settings
from app.database import get_db_session
from app.embeddings import (
    EmbeddingProvider,
    EmbeddingServiceError,
    OpenRouterEmbeddingProvider,
    UnconfiguredEmbeddingProvider,
)
from app.evaluation import RetrievalEvaluationService
from app.file_processing import FileProcessingError, safe_upload_path
from app.llm import (
    LLMServiceError,
    MeetingSummarizer,
    OpenRouterMeetingSummarizer,
    UnconfiguredMeetingSummarizer,
)
from app.models import ProcessingJob, User
from app.observability import configure_observability
from app.repository import (
    AgentRepository,
    JobRepository,
    MeetingRepository,
    UserRepository,
)
from app.schemas import (
    AgentMessageRequest,
    AgentRunResponse,
    AgentThreadCreateRequest,
    AgentThreadResponse,
    AgentTurnResponse,
    AnswerResponse,
    EvaluationRequest,
    EvaluationResponse,
    HealthResponse,
    JobListResponse,
    JobResponse,
    LoginRequest,
    MeetingCreateRequest,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdateRequest,
    QuestionRequest,
    SummaryRequest,
    SummaryResponse,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
)
from app.security import (
    AuthenticationError,
    FieldCipher,
    PasswordService,
    TokenService,
)
from app.services import (
    MeetingIngestionService,
    MeetingNotFoundError,
    NoSearchResultsError,
    RetrievalAnswerService,
)

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.state.cipher = FieldCipher(settings.field_encryption_key)
    app.state.tokens = TokenService(
        settings.app_secret_key, settings.access_token_minutes
    )
    app.state.passwords = PasswordService()
    if settings.openrouter_api_key:
        app.state.summarizer = OpenRouterMeetingSummarizer(settings)
        app.state.embedding_provider = OpenRouterEmbeddingProvider(settings)
    else:
        logger.warning("OPENROUTER_API_KEY is not configured.")
        app.state.summarizer = UnconfiguredMeetingSummarizer()
        app.state.embedding_provider = UnconfiguredEmbeddingProvider()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Authenticated, encrypted meeting intelligence and RAG API.",
    lifespan=lifespan,
)
configure_observability(app, settings)

DatabaseDependency = Annotated[Session, Depends(get_db_session)]


def get_summarizer(request: Request) -> MeetingSummarizer:
    return cast(MeetingSummarizer, request.app.state.summarizer)


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    return cast(EmbeddingProvider, request.app.state.embedding_provider)


def get_cipher(request: Request) -> FieldCipher:
    return cast(FieldCipher, request.app.state.cipher)


SummarizerDependency = Annotated[MeetingSummarizer, Depends(get_summarizer)]
EmbeddingDependency = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
CipherDependency = Annotated[FieldCipher, Depends(get_cipher)]


def get_auth_service(request: Request, session: DatabaseDependency) -> AuthService:
    return AuthService(
        UserRepository(session),
        cast(PasswordService, request.app.state.passwords),
        cast(TokenService, request.app.state.tokens),
    )


AuthDependency = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(
    request: Request,
    session: DatabaseDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Bearer access token is required.")
    tokens = cast(TokenService, request.app.state.tokens)
    user_id = tokens.decode_user_id(credentials.credentials)
    return AuthService(
        UserRepository(session),
        cast(PasswordService, request.app.state.passwords),
        tokens,
    ).current_user(user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_ingestion_service(
    session: DatabaseDependency,
    embeddings: EmbeddingDependency,
    cipher: CipherDependency,
) -> MeetingIngestionService:
    return MeetingIngestionService(
        MeetingRepository(session, cipher), embeddings, settings
    )


IngestionDependency = Annotated[MeetingIngestionService, Depends(get_ingestion_service)]


def get_retrieval_service(
    session: DatabaseDependency,
    embeddings: EmbeddingDependency,
    summarizer: SummarizerDependency,
    cipher: CipherDependency,
) -> RetrievalAnswerService:
    return RetrievalAnswerService(
        MeetingRepository(session, cipher), embeddings, summarizer, settings
    )


RetrievalDependency = Annotated[RetrievalAnswerService, Depends(get_retrieval_service)]


def get_evaluation_service(
    session: DatabaseDependency,
    embeddings: EmbeddingDependency,
    cipher: CipherDependency,
) -> RetrievalEvaluationService:
    return RetrievalEvaluationService(MeetingRepository(session, cipher), embeddings)


EvaluationDependency = Annotated[
    RetrievalEvaluationService, Depends(get_evaluation_service)
]


def get_agent_workflow(
    session: DatabaseDependency,
    embeddings: EmbeddingDependency,
    summarizer: SummarizerDependency,
    cipher: CipherDependency,
) -> StatefulAgentWorkflow:
    return StatefulAgentWorkflow(
        AgentRepository(session, cipher),
        MeetingRepository(session, cipher),
        embeddings,
        summarizer,
        settings,
    )


AgentDependency = Annotated[StatefulAgentWorkflow, Depends(get_agent_workflow)]


def error(status: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail})


@app.exception_handler(AuthenticationError)
async def handle_auth(_: Request, exc: AuthenticationError) -> JSONResponse:
    return error(401, str(exc))


@app.exception_handler(UserAlreadyExistsError)
async def handle_conflict(_: Request, exc: UserAlreadyExistsError) -> JSONResponse:
    return error(409, str(exc))


@app.exception_handler(LLMServiceError)
async def handle_llm(_: Request, exc: LLMServiceError) -> JSONResponse:
    return error(502, str(exc))


@app.exception_handler(EmbeddingServiceError)
async def handle_embedding(_: Request, exc: EmbeddingServiceError) -> JSONResponse:
    return error(502, str(exc))


@app.exception_handler(FileProcessingError)
async def handle_file(_: Request, exc: FileProcessingError) -> JSONResponse:
    return error(400, str(exc))


@app.exception_handler(OperationalError)
async def handle_database(_: Request, exc: OperationalError) -> JSONResponse:
    logger.error("Database operation failed: %s", exc)
    return error(503, "The meeting database is temporarily unavailable.")


@app.exception_handler(IntegrityError)
async def handle_integrity(_: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("Database integrity error: %s", exc)
    return error(409, "The requested database change conflicts with existing data.")


@app.exception_handler(MeetingNotFoundError)
async def handle_not_found(_: Request, exc: MeetingNotFoundError) -> JSONResponse:
    return error(404, str(exc))


@app.exception_handler(NoSearchResultsError)
async def handle_no_results(_: Request, exc: NoSearchResultsError) -> JSONResponse:
    return error(404, str(exc))


@app.get("/health", response_model=HealthResponse, tags=["Operations"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@app.post("/auth/register", response_model=UserResponse, status_code=201)
def register(request: UserCreateRequest, service: AuthDependency) -> UserResponse:
    return service.register(request.email, request.password)


@app.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, service: AuthDependency) -> TokenResponse:
    return service.login(request.email, request.password)


@app.get("/auth/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return AuthService.response(user)


@app.post("/summaries", response_model=SummaryResponse)
def create_summary(
    request: SummaryRequest,
    summarizer: SummarizerDependency,
    _: CurrentUser,
) -> SummaryResponse:
    return SummaryResponse(
        result=summarizer.summarize(request.text),
        model=summarizer.model_name,
    )


@app.post("/meetings", response_model=MeetingResponse, status_code=201)
def create_meeting(
    request: MeetingCreateRequest,
    service: IngestionDependency,
    user: CurrentUser,
) -> MeetingResponse:
    return service.ingest(user.id, request.title, request.transcript)


@app.get("/meetings", response_model=MeetingListResponse)
def list_meetings(
    service: IngestionDependency,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MeetingListResponse:
    return service.list_for_owner(user.id, limit, offset)


@app.get("/meetings/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: uuid.UUID,
    service: IngestionDependency,
    user: CurrentUser,
) -> MeetingResponse:
    return service.get(meeting_id, user.id)


@app.patch("/meetings/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: uuid.UUID,
    request: MeetingUpdateRequest,
    service: IngestionDependency,
    user: CurrentUser,
) -> MeetingResponse:
    return service.update(meeting_id, user.id, request.title, request.transcript)


@app.delete("/meetings/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: uuid.UUID,
    service: IngestionDependency,
    user: CurrentUser,
) -> None:
    service.delete(meeting_id, user.id)


@app.post("/meetings/{meeting_id}/reindex", response_model=MeetingResponse)
def reindex_meeting(
    meeting_id: uuid.UUID,
    service: IngestionDependency,
    user: CurrentUser,
) -> MeetingResponse:
    return service.reindex(meeting_id, user.id)


@app.post("/questions", response_model=AnswerResponse)
def answer_question(
    request: QuestionRequest,
    service: RetrievalDependency,
    user: CurrentUser,
) -> AnswerResponse:
    return service.answer(user.id, request.question, request.meeting_id, request.top_k)


def job_response(job: ProcessingJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        kind=job.kind,
        status=job.status,
        original_filename=job.original_filename,
        title=job.title,
        meeting_id=job.meeting_id,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def get_job_repository(session: DatabaseDependency) -> JobRepository:
    return JobRepository(session)


JobDependency = Annotated[JobRepository, Depends(get_job_repository)]


async def queue_upload(
    upload: UploadFile,
    title: str,
    kind: str,
    suffixes: set[str],
    user: User,
    session: Session,
) -> JobResponse:
    filename = upload.filename or f"upload.{kind}"
    path = safe_upload_path(settings.upload_dir, filename, suffixes)
    size = 0
    try:
        with path.open("wb") as destination:
            while content := await upload.read(1024 * 1024):
                size += len(content)
                if size > settings.max_upload_bytes:
                    raise FileProcessingError("Uploaded file is too large.")
                destination.write(content)
        jobs = JobRepository(session)
        job = jobs.create(user.id, kind, filename, str(path), title, size)
        try:
            celery_app.send_task("process_upload", args=[str(job.id)])
        except Exception as exc:
            jobs.set_status(job, "failed", error="Background queue unavailable.")
            raise FileProcessingError("Background queue is unavailable.") from exc
        return job_response(job)
    except Exception:
        path.unlink(missing_ok=True)
        raise


@app.post("/uploads/pdf", response_model=JobResponse, status_code=202)
async def upload_pdf(
    user: CurrentUser,
    session: DatabaseDependency,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=3, max_length=300)],
) -> JobResponse:
    return await queue_upload(file, title, "pdf", {".pdf"}, user, session)


@app.post("/uploads/audio", response_model=JobResponse, status_code=202)
async def upload_audio(
    user: CurrentUser,
    session: DatabaseDependency,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=3, max_length=300)],
) -> JobResponse:
    return await queue_upload(
        file,
        title,
        "audio",
        {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".mp4"},
        user,
        session,
    )


@app.get("/jobs", response_model=JobListResponse)
def list_jobs(
    jobs: JobDependency,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListResponse:
    items, total = jobs.list_for_owner(user.id, limit, offset)
    return JobListResponse(
        items=[job_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: uuid.UUID,
    user: CurrentUser,
    jobs: JobDependency,
) -> JobResponse:
    job = jobs.get(job_id, user.id)
    if not job:
        raise MeetingNotFoundError(f"Job {job_id} was not found.")
    return job_response(job)


@app.post("/evaluations/retrieval", response_model=EvaluationResponse)
def evaluate_retrieval(
    request: EvaluationRequest,
    service: EvaluationDependency,
    user: CurrentUser,
) -> EvaluationResponse:
    return service.evaluate(user.id, request.cases, request.top_k)


def agent_thread_response(thread, repository: AgentRepository) -> AgentThreadResponse:
    return AgentThreadResponse(
        id=thread.id,
        title=thread.title,
        status=thread.status,
        state=thread.state,
        meeting_id=thread.meeting_id,
        turns=[
            AgentTurnResponse(
                id=turn.id,
                role=turn.role,
                content=repository.turn_content(turn),
                state=turn.state,
                trace_id=turn.trace_id,
                input_tokens=turn.input_tokens,
                output_tokens=turn.output_tokens,
                estimated_cost_usd=float(turn.estimated_cost_usd),
                created_at=turn.created_at,
            )
            for turn in thread.turns
        ],
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@app.post("/agent/threads", response_model=AgentThreadResponse, status_code=201)
def create_agent_thread(
    request: AgentThreadCreateRequest,
    user: CurrentUser,
    session: DatabaseDependency,
    cipher: CipherDependency,
) -> AgentThreadResponse:
    meetings = MeetingRepository(session, cipher)
    if request.meeting_id and not meetings.get(request.meeting_id, user.id):
        raise MeetingNotFoundError(f"Meeting {request.meeting_id} was not found.")
    repository = AgentRepository(session, cipher)
    thread = repository.create_thread(user.id, request.title, request.meeting_id)
    return agent_thread_response(thread, repository)


@app.get("/agent/threads/{thread_id}", response_model=AgentThreadResponse)
def get_agent_thread(
    thread_id: uuid.UUID,
    user: CurrentUser,
    session: DatabaseDependency,
    cipher: CipherDependency,
) -> AgentThreadResponse:
    repository = AgentRepository(session, cipher)
    thread = repository.get_thread(thread_id, user.id)
    if not thread:
        raise MeetingNotFoundError(f"Agent thread {thread_id} was not found.")
    return agent_thread_response(thread, repository)


@app.post("/agent/threads/{thread_id}/messages", response_model=AgentRunResponse)
def send_agent_message(
    thread_id: uuid.UUID,
    request: AgentMessageRequest,
    workflow: AgentDependency,
    user: CurrentUser,
) -> AgentRunResponse:
    return workflow.run(thread_id, user.id, request.message)
