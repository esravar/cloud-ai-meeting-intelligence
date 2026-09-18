import re
import uuid

from opentelemetry import trace

from app.config import Settings
from app.embeddings import EmbeddingProvider
from app.llm import LLMServiceError, MeetingSummarizer
from app.observability import current_trace_id, transition
from app.repository import AgentRepository, MeetingRepository
from app.schemas import AgentRunResponse, Citation
from app.services import MeetingNotFoundError, NoSearchResultsError


class StatefulAgentWorkflow:
    """A persisted retrieve -> answer -> wait state machine."""

    def __init__(
        self,
        agents: AgentRepository,
        meetings: MeetingRepository,
        embeddings: EmbeddingProvider,
        summarizer: MeetingSummarizer,
        settings: Settings,
    ):
        self._agents = agents
        self._meetings = meetings
        self._embeddings = embeddings
        self._summarizer = summarizer
        self._settings = settings

    def run(
        self, thread_id: uuid.UUID, owner_id: uuid.UUID, message: str
    ) -> AgentRunResponse:
        thread = self._agents.get_thread(thread_id, owner_id)
        if not thread:
            raise MeetingNotFoundError(f"Agent thread {thread_id} was not found.")

        history = self._agents.history(thread, self._settings.agent_history_turns)
        trace_id = current_trace_id()
        previous = thread.state
        self._agents.add_turn(thread, "user", message, "retrieving", trace_id)
        transition(previous, "retrieving")

        try:
            with trace.get_tracer(__name__).start_as_current_span("agent.retrieve"):
                vector = self._embeddings.embed_query(message)
                chunks = self._meetings.search(
                    owner_id,
                    vector,
                    self._embeddings.model_name,
                    self._embeddings.dimensions,
                    self._settings.retrieval_top_k,
                    thread.meeting_id,
                )
            if not chunks:
                raise NoSearchResultsError("No compatible meeting excerpts were found.")

            transition("retrieving", "answering")
            self._agents.set_state(thread, "answering", "running")
            answer, usage = self._summarizer.answer_with_history(
                message, [chunk.content for chunk in chunks], history
            )
            references = {int(value) for value in re.findall(r"\[(\d+)]", answer)}
            if not references or any(index > len(chunks) for index in references):
                raise LLMServiceError("Agent answer contained invalid citations.")

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
                for index, chunk in enumerate(chunks, 1)
                if index in references
            ]
            trace_id = current_trace_id()
            self._agents.add_turn(
                thread, "assistant", answer, "waiting_for_user", trace_id, usage
            )
            self._agents.set_state(thread, "waiting_for_user", "ready")
            transition("answering", "waiting_for_user")
            return AgentRunResponse(
                thread_id=thread.id,
                state="waiting_for_user",
                answer=answer,
                citations=citations,
                trace_id=trace_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                estimated_cost_usd=usage.estimated_cost_usd,
            )
        except Exception:
            failed_from = thread.state
            self._agents.set_state(thread, "failed", "failed")
            transition(failed_from, "failed")
            raise
