import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.config import Settings

HTTP_REQUESTS = Counter(
    "meeting_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "meeting_http_request_duration_seconds", "HTTP request latency", ["method", "route"]
)
AI_CALLS = Counter(
    "meeting_ai_calls_total", "AI provider calls", ["operation", "model", "status"]
)
AI_LATENCY = Histogram(
    "meeting_ai_call_duration_seconds", "AI provider latency", ["operation", "model"]
)
AI_TOKENS = Counter(
    "meeting_ai_tokens_total", "AI tokens", ["operation", "model", "type"]
)
AI_COST = Counter(
    "meeting_ai_estimated_cost_usd_total",
    "Estimated AI cost in USD",
    ["operation", "model"],
)
AGENT_TRANSITIONS = Counter(
    "meeting_agent_state_transitions_total",
    "Agent workflow transitions",
    ["from_state", "to_state"],
)


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


def configure_observability(app: FastAPI, settings: Settings) -> None:
    if settings.otel_exporter_otlp_endpoint:
        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.otel_service_name})
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
            )
        )
        trace.set_tracer_provider(provider)

    @app.middleware("http")
    async def observe_http(request: Request, call_next):
        started = time.perf_counter()
        status = 500
        with trace.get_tracer(__name__).start_as_current_span(
            f"{request.method} {request.url.path}"
        ) as span:
            try:
                response = await call_next(request)
                status = response.status_code
                return response
            finally:
                route = getattr(request.scope.get("route"), "path", request.url.path)
                elapsed = time.perf_counter() - started
                HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
                HTTP_LATENCY.labels(request.method, route).observe(elapsed)
                span.set_attribute("http.request.method", request.method)
                span.set_attribute("http.route", route)
                span.set_attribute("http.response.status_code", status)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def current_trace_id() -> str | None:
    context = trace.get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else None


def estimate_cost(settings: Settings, input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * settings.llm_input_cost_per_million
        + output_tokens * settings.llm_output_cost_per_million
    ) / 1_000_000


@contextmanager
def observe_ai(operation: str, model: str) -> Iterator[dict[str, int | float]]:
    values: dict[str, int | float] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": 0.0,
    }
    started = time.perf_counter()
    status = "error"
    with trace.get_tracer(__name__).start_as_current_span(f"ai.{operation}") as span:
        span.set_attribute("gen_ai.operation.name", operation)
        span.set_attribute("gen_ai.request.model", model)
        try:
            yield values
            status = "ok"
        finally:
            AI_CALLS.labels(operation, model, status).inc()
            AI_LATENCY.labels(operation, model).observe(time.perf_counter() - started)
            AI_TOKENS.labels(operation, model, "input").inc(values["input_tokens"])
            AI_TOKENS.labels(operation, model, "output").inc(values["output_tokens"])
            AI_COST.labels(operation, model).inc(values["cost"])
            span.set_attribute("gen_ai.usage.input_tokens", values["input_tokens"])
            span.set_attribute("gen_ai.usage.output_tokens", values["output_tokens"])
            span.set_attribute("gen_ai.usage.cost_usd", values["cost"])


def transition(from_state: str, to_state: str) -> None:
    AGENT_TRANSITIONS.labels(from_state, to_state).inc()
    span = trace.get_current_span()
    span.add_event("agent.state_transition", {"from": from_state, "to": to_state})
