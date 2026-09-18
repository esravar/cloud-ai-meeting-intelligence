import json
import logging
from typing import Protocol

from openai import OpenAI
from pydantic import ValidationError

from app.config import Settings
from app.observability import Usage, estimate_cost, observe_ai
from app.schemas import MeetingSummary

logger = logging.getLogger(__name__)


class LLMServiceError(RuntimeError):
    """Raised when the language model cannot produce a valid response."""


class MeetingSummarizer(Protocol):
    model_name: str

    def summarize(self, text: str) -> MeetingSummary: ...

    def answer_question(self, question: str, contexts: list[str]) -> str: ...

    def answer_with_history(
        self, question: str, contexts: list[str], history: list[tuple[str, str]]
    ) -> tuple[str, Usage]: ...


class UnconfiguredMeetingSummarizer:
    model_name = "unconfigured"

    def summarize(self, text: str) -> MeetingSummary:
        raise LLMServiceError("OPENROUTER_API_KEY is not configured.")

    def answer_question(self, question: str, contexts: list[str]) -> str:
        raise LLMServiceError("OPENROUTER_API_KEY is not configured.")

    def answer_with_history(self, question, contexts, history):
        raise LLMServiceError("OPENROUTER_API_KEY is not configured.")


class OpenRouterMeetingSummarizer:
    def __init__(self, settings: Settings):
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured.")

        self.model_name = settings.openrouter_model
        self._settings = settings
        self._client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    def summarize(self, text: str) -> MeetingSummary:
        try:
            with observe_ai("summarize", self.model_name) as observed:
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You analyze enterprise meeting transcripts. Return only "
                                "valid JSON with these fields: summary (string), decisions "
                                "(array of strings), action_items (array of objects with "
                                "description, owner, and due_date), and risks (array of "
                                "strings). Use null when an owner or due date is unknown. "
                                "Never invent facts that are not present in the transcript."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Analyze this meeting transcript:\n\n{text}",
                        },
                    ],
                )
                self._record_usage(response, observed)
            content = response.choices[0].message.content
            if not content:
                raise LLMServiceError("The language model returned an empty response.")
            return MeetingSummary.model_validate(json.loads(content))
        except LLMServiceError:
            raise
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("The language model returned invalid structured output.")
            raise LLMServiceError(
                "The language model returned an invalid structured response."
            ) from exc
        except Exception as exc:
            logger.exception("Language model request failed.")
            raise LLMServiceError("The language model request failed.") from exc

    def answer_question(self, question: str, contexts: list[str]) -> str:
        answer, _ = self.answer_with_history(question, contexts, [])
        return answer

    def answer_with_history(
        self, question: str, contexts: list[str], history: list[tuple[str, str]]
    ) -> tuple[str, Usage]:
        formatted_context = "\n\n".join(
            f"[{index}] {context}" for index, context in enumerate(contexts, start=1)
        )
        try:
            history_text = "\n".join(
                f"{role.capitalize()}: {content}" for role, content in history
            )
            with observe_ai("agent_answer", self.model_name) as observed:
                response = self._client.chat.completions.create(
                    model=self.model_name,
                    temperature=0.1,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Answer questions using only the supplied meeting excerpts. "
                                "Cite supporting excerpts using square-bracket source numbers "
                                "such as [1]. If the excerpts do not contain the answer, say "
                                "that the available meeting records do not provide enough "
                                "information. Do not use outside knowledge."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Previous conversation:\n{history_text or '(none)'}\n\n"
                                f"Question: {question}\n\n"
                                f"Meeting excerpts:\n{formatted_context}"
                            ),
                        },
                    ],
                )
                usage = self._record_usage(response, observed)
            content = response.choices[0].message.content
            if not content:
                raise LLMServiceError("The language model returned an empty response.")
            return content.strip(), usage
        except LLMServiceError:
            raise
        except Exception as exc:
            logger.exception("Grounded answer request failed.")
            raise LLMServiceError("The language model request failed.") from exc

    def _record_usage(self, response, observed: dict) -> Usage:
        raw = getattr(response, "usage", None)
        input_tokens = int(raw.prompt_tokens or 0) if raw else 0
        output_tokens = int(raw.completion_tokens or 0) if raw else 0
        cost = estimate_cost(self._settings, input_tokens, output_tokens)
        observed.update(
            input_tokens=input_tokens, output_tokens=output_tokens, cost=cost
        )
        return Usage(input_tokens, output_tokens, cost)
