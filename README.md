# Cloud AI Meeting Intelligence

Cloud AI Meeting Intelligence is a production-oriented backend for turning
meeting documents and recordings into searchable organizational knowledge. It
accepts text, PDF, and audio sources; processes long-running uploads in the
background; stores encrypted transcripts and vector embeddings; and answers
questions with verifiable citations to the original meeting content.

The project goes beyond a basic LLM demo. It combines authenticated,
user-isolated data access with stateful agent conversations, PostgreSQL and
pgvector retrieval, Redis-backed background jobs, observability, automated
tests, containerization, and Kubernetes deployment manifests.

OpenRouter is currently used as the LLM and embedding gateway, while the
provider interfaces remain replaceable so additional hosted or local models
can be introduced without changing the public API.

## End-to-end workflow

```text
Register / Login
       |
       v
Upload PDF or audio ---> Redis queue ---> Celery processing
                                             |
                                             v
                              Extract / transcribe / encrypt
                                             |
                                             v
                                  Chunk and create embeddings
                                             |
                                             v
                                  PostgreSQL + pgvector
                                             |
                    +------------------------+---------------------+
                    |                                              |
                    v                                              v
          Grounded Q&A with citations                 Stateful agent chat
```

## Technology stack

| Area | Technologies |
| --- | --- |
| API | FastAPI, Pydantic, Uvicorn |
| Data | PostgreSQL, SQLAlchemy, Alembic, pgvector |
| AI and retrieval | OpenRouter, embeddings, HNSW cosine search, RAG |
| Background processing | Celery, Redis |
| Security | JWT, Argon2, Fernet encryption, per-user ownership |
| Observability | OpenTelemetry, Prometheus metrics, trace IDs |
| Delivery | Docker Compose, GitHub Actions, Kubernetes |
| Quality | Pytest, Ruff, retrieval evaluation, citation validation |

## Current capabilities

- Typed FastAPI endpoints with OpenAPI documentation
- Structured and validated meeting analysis
- Configurable OpenRouter model
- Provider-independent LLM and embedding interfaces
- PostgreSQL and pgvector knowledge base
- Batch embedding and overlapping transcript chunking
- HNSW cosine-similarity retrieval
- Grounded answers with meeting and chunk citations
- JWT authentication and per-user data ownership
- Argon2 password hashing
- Fernet encryption for transcripts and retrieved chunk text at rest
- Meeting update, delete, and reindex operations
- PDF and audio upload jobs through Celery and Redis
- Retrieval hit-rate and mean reciprocal rank evaluation
- Citation post-validation
- Explicit transaction rollback on database failures
- Alembic database migrations
- Centralized upstream error handling
- Transcript length and content validation
- Automated API and LLM parsing tests
- Non-root Docker image with a health check
- GitHub Actions lint and test workflow
- Stateful, PostgreSQL-backed agent conversations
- OpenTelemetry traces and Prometheus latency/token/cost metrics
- Kubernetes API, worker, migration, Redis, ingress, HPA, and PDB manifests

## Frontend preview

The responsive, bilingual frontend is currently in development. It will connect
the existing FastAPI, PostgreSQL/pgvector, Redis, Celery, RAG, and stateful-agent
backend to a production web interface.

> These screenshots are design previews created with mock data. Model names,
> user details, document counts, latency values, and usage metrics shown in the
> designs are illustrative. Live FastAPI integration is in progress.

### Dashboard

Recent meetings, background jobs, processing states, and quick AI actions.

![Meeting Intelligence dashboard](assets/screenshots/dashboard-tr.png)

### Meeting library

Searchable and paginated PDF, audio, and text meeting records.

![Meeting Intelligence meeting library](assets/screenshots/meetings-tr.png)

### Grounded question answering

RAG-based answers with retrieved excerpts, relevance scores, and citations.

![Meeting Intelligence grounded question answering](assets/screenshots/ask-ai-tr.png)

### Stateful agent conversations

Persistent follow-up conversations with workflow state and grounded references.

![Meeting Intelligence stateful agent chat](assets/screenshots/agent-chat-tr.png)

### English and Turkish interface

The frontend is designed to support complete English and Turkish localization.

![Meeting Intelligence English interface](assets/screenshots/ask-ai-en.png)

### Live demo

🚧 **Frontend implementation and API integration are in progress. A public,
interactive URL will be added here after deployment.**

The working frontend source is in [`frontend/`](frontend/). It implements
authentication, meetings, upload jobs, cited Q&A, and agent conversations
against the FastAPI API. The Stitch images above remain design references;
the application does not display their mock counts or mock AI answers.

Frontend progress:

- [x] UX and responsive visual design
- [x] Dashboard, meetings, grounded Q&A, and agent-chat concepts
- [x] English and Turkish interface designs
- [x] Frontend component implementation
- [x] FastAPI authentication and API integration
- [x] Upload and background-job polling
- [ ] Netlify deployment
- [ ] Public backend, custom domain, CORS, and HTTPS

## Architecture

```text
                         +-----------------------+
Transcript -----------> | FastAPI ingestion API |
                         +-----------+-----------+
                                     |
                              chunk + embed
                                     |
                                     v
                         +-----------------------+
                         | PostgreSQL + pgvector |
                         +-----------+-----------+
                                     ^
                                     |
Question ---> embed ---> vector search
                                     |
                                     v
                         +-----------------------+
                         | Grounded LLM answer   |
                         | with citations        |
                         +-----------------------+
```

## Local setup

Requirements:

- Python 3.11+
- PostgreSQL 16 with pgvector
- An OpenRouter API key
- Redis for background file jobs
- An OpenAI API key when audio transcription is enabled

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Generate production secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `APP_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `OPENROUTER_API_KEY`, and the
database credentials in `.env`. Then create the schema and start the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

### Local PostgreSQL with Postgres.app

Postgres.app includes the pgvector extension. After initializing and starting
the local PostgreSQL server, create the project role and database:

```bash
psql postgres
```

```sql
CREATE ROLE meeting WITH LOGIN PASSWORD 'meeting';
CREATE DATABASE meeting_intelligence OWNER meeting;
\c meeting_intelligence
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

The default development connection string is:

```text
postgresql+psycopg://meeting:meeting@localhost:5432/meeting_intelligence
```

Apply the schema and verify the current migration:

```bash
alembic upgrade head
alembic current
```

Open:

- API documentation: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

## API example

```bash
curl -X POST http://localhost:8000/summaries \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The team approved the Friday release. Esra will prepare the release checklist. Monitoring remains a risk."
  }'
```

Example response:

```json
{
  "result": {
    "summary": "The team approved the Friday release.",
    "decisions": ["Release the product on Friday."],
    "action_items": [
      {
        "description": "Prepare the release checklist.",
        "owner": "Esra",
        "due_date": "Friday"
      }
    ],
    "risks": ["Monitoring is not ready."]
  },
  "model": "google/gemma-4-26b-a4b-it:free"
}
```

Register and log in before accessing protected endpoints:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"esra@example.com","password":"a-long-unique-password"}'

curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"esra@example.com","password":"a-long-unique-password"}'
```

## RAG workflow

Store and embed a meeting:

```bash
curl -X POST http://localhost:8000/meetings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Architecture Review",
    "transcript": "The team selected PostgreSQL with pgvector. Esra will prepare the deployment checklist by Thursday."
  }'
```

Ask a grounded question across stored meetings:

```bash
curl -X POST http://localhost:8000/questions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which database was selected and who owns the deployment checklist?",
    "top_k": 5
  }'
```

The answer includes numbered inline references and structured citation metadata:

```json
{
  "answer": "The team selected PostgreSQL with pgvector [1]. Esra owns the deployment checklist [1].",
  "citations": [
    {
      "index": 1,
      "meeting_id": "7d2cc622-887a-49a2-a381-b8cbf6279136",
      "meeting_title": "Architecture Review",
      "chunk_id": "21630e91-4f18-469c-a97a-796824bbca5a",
      "chunk_index": 0,
      "score": 0.93,
      "excerpt": "The team selected PostgreSQL with pgvector..."
    }
  ],
  "model": "google/gemma-4-26b-a4b-it:free"
}
```

Pass `meeting_id` in the question request to restrict retrieval to one meeting.
Only meetings owned by the authenticated user are searchable.

Update, delete, or rebuild embeddings:

```text
GET    /meetings?limit=20&offset=0
PATCH  /meetings/{meeting_id}
DELETE /meetings/{meeting_id}
POST   /meetings/{meeting_id}/reindex
```

`GET /meetings` returns the authenticated user's meetings newest-first with
`items`, `total`, `limit`, and `offset` fields for dashboard pagination.

Every meeting records the embedding model and dimension used to create its
vectors. Retrieval excludes incompatible vectors until the meeting is
reindexed.

## PDF and audio jobs

Uploads return immediately with `202 Accepted`; Celery workers process them
outside the HTTP request:

```text
POST /uploads/pdf
POST /uploads/audio
GET  /jobs?limit=20&offset=0
GET  /jobs/{job_id}
```

`GET /jobs` returns only the authenticated user's upload jobs, newest-first,
using the same pagination envelope as the meetings endpoint.

PDF extraction supports text-based PDFs. Scanned PDFs report that OCR is
required. Audio transcription uses the OpenAI Transcription API and defaults to
`gpt-4o-mini-transcribe`.

Uploaded files are deleted after successful or failed processing. Extracted
transcripts and chunks are encrypted before PostgreSQL storage.

## Retrieval evaluation

`POST /evaluations/retrieval` accepts question/expected-meeting pairs and
returns:

- hit rate at K
- mean reciprocal rank

These metrics test whether retrieval surfaces the expected meeting before an
LLM generates an answer.

## Stateful agent workflow

Agent conversations survive API restarts because threads, encrypted messages,
workflow state, trace IDs, tokens, and estimated cost are stored in PostgreSQL.
The explicit state machine is:

```text
waiting_for_user -> retrieving -> answering -> waiting_for_user
                                      |
                                      +-> failed
```

Create a thread, optionally restricting it to one meeting, and continue it:

```bash
curl -X POST http://localhost:8000/agent/threads \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Architecture assistant","meeting_id":null}'

curl -X POST http://localhost:8000/agent/threads/$THREAD_ID/messages \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"What did we decide about deployment?"}'

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/agent/threads/$THREAD_ID
```

The most recent `AGENT_HISTORY_TURNS` messages are supplied to the model. RAG
still limits factual grounding to retrieved meeting excerpts and validates all
numbered citations.

## Observability

Every HTTP request and AI operation records latency. Agent transitions emit
trace events. Prometheus metrics are available from `GET /metrics`, including:

- `meeting_http_request_duration_seconds`
- `meeting_ai_call_duration_seconds`
- `meeting_ai_tokens_total`
- `meeting_ai_estimated_cost_usd_total`
- `meeting_agent_state_transitions_total`

Set `OTEL_EXPORTER_OTLP_ENDPOINT` to send traces to an OpenTelemetry Collector.
Set the two `LLM_*_COST_PER_MILLION` values to the current provider price; cost
is deliberately configurable because provider/model pricing changes. Trace IDs
are returned by agent runs and stored with turns, allowing one user-visible
answer to be matched to its distributed trace.

## Tests and linting

Tests do not make external LLM calls.

```bash
pytest -q
ruff check .
```

## Docker

The container workflow starts API, PostgreSQL/pgvector, Redis, Celery worker,
and migrations together. Required secrets use Compose's fail-fast syntax:

```bash
docker compose up --build
```

## Kubernetes and cloud deployment

The manifests in `k8s/` are provider-neutral. Before deployment:

1. Push the image and replace `ghcr.io/your-org/meeting-intelligence:latest`.
2. Use managed PostgreSQL with pgvector and managed Redis in production when
   available. The included Redis is suitable for learning and small workloads.
3. Copy `k8s/secret.example.yaml` outside version control, replace every value,
   and apply it. Never commit the resulting secret.
4. Ensure the cluster has an RWX StorageClass, metrics-server, and an nginx
   ingress controller; otherwise adjust/remove the PVC, HPA, or ingress.
5. Replace `meeting.example.com` and configure TLS for the ingress.

Apply in this order so schema migration completes before traffic moves:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f /safe/path/meeting-secret.yaml
kubectl apply -k k8s
kubectl -n meeting-intelligence wait --for=condition=complete job/meeting-migration --timeout=180s
kubectl -n meeting-intelligence rollout status deployment/api
kubectl -n meeting-intelligence rollout status deployment/worker
```

The included collector accepts OTLP traces and logs them. In a real cloud
environment, replace its `debug` exporter with your tracing backend exporter.
Prometheus can discover the API through its pod scrape annotations.

## Remaining cloud hardening

- Store uploads in object storage instead of a shared filesystem.
- Use a managed secret store/External Secrets rather than plain Kubernetes Secrets.
- Autoscale Celery workers from Redis queue depth with KEDA.
- Export traces and metrics to a retained production backend and add alerts.
