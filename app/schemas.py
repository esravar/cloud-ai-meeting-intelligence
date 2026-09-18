import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class SummaryRequest(BaseModel):
    text: str = Field(
        min_length=20,
        max_length=100_000,
        description="Meeting transcript to analyze.",
    )

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Meeting transcript cannot be blank.")
        return normalized


class ActionItem(BaseModel):
    description: str
    owner: str | None = None
    due_date: str | None = None


class MeetingSummary(BaseModel):
    summary: str
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    result: MeetingSummary
    model: str


class HealthResponse(BaseModel):
    status: str
    version: str


class ErrorResponse(BaseModel):
    detail: str


class MeetingCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    transcript: str = Field(min_length=20, max_length=500_000)

    @field_validator("title", "transcript")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be blank.")
        return normalized


class MeetingResponse(BaseModel):
    id: uuid.UUID
    title: str
    chunk_count: int
    source_type: str
    source_name: str | None
    embedding_model: str
    created_at: datetime
    updated_at: datetime


class MeetingListResponse(BaseModel):
    items: list[MeetingResponse]
    total: int
    limit: int
    offset: int


class MeetingUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    transcript: str | None = Field(default=None, min_length=20, max_length=500_000)

    @field_validator("title", "transcript")
    @classmethod
    def optional_content_must_not_be_blank(cls, value: str | None):
        if value is not None and not value.strip():
            raise ValueError("Value cannot be blank.")
        return value.strip() if value is not None else None


class QuestionRequest(BaseModel):
    question: str = Field(min_length=5, max_length=2_000)
    meeting_id: uuid.UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Question cannot be blank.")
        return normalized


class Citation(BaseModel):
    index: int
    meeting_id: uuid.UUID
    meeting_title: str
    chunk_id: uuid.UUID
    chunk_index: int
    score: float
    excerpt: str


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    model: str


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class JobResponse(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    original_filename: str
    title: str
    meeting_id: uuid.UUID | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
    limit: int
    offset: int


class EvaluationCase(BaseModel):
    question: str
    expected_meeting_id: uuid.UUID


class EvaluationRequest(BaseModel):
    cases: list[EvaluationCase] = Field(min_length=1, max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)


class EvaluationResponse(BaseModel):
    case_count: int
    hit_rate_at_k: float
    mean_reciprocal_rank: float


class AgentThreadCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    meeting_id: uuid.UUID | None = None


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=3, max_length=2_000)


class AgentTurnResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    state: str
    trace_id: str | None
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    created_at: datetime


class AgentThreadResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    state: str
    meeting_id: uuid.UUID | None
    turns: list[AgentTurnResponse]
    created_at: datetime
    updated_at: datetime


class AgentRunResponse(BaseModel):
    thread_id: uuid.UUID
    state: str
    answer: str
    citations: list[Citation]
    trace_id: str | None
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
