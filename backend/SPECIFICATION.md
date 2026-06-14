# Backend Service Specification

**Status:** Implemented and verified MVP.

The `backend/` module is the FastAPI BFF between the Vue frontend and the external Agent Service.
It implements the frozen frontend contract in `api/openapi.yaml` and the Backend Internal Tool API
in `agent-service/internal-tools-openapi.yaml`. The Agent Service itself is not implemented here.
The supported ASGI entry point is `app.main:app`; `app/` is a two-file ASGI facade, while all
runtime implementation lives in the installable `travel_backend` package.

## Responsibilities

- JWT access authentication, rotating hashed refresh tokens, and user ownership checks.
- Persistent users, sessions, runs, messages, groups, plans, map points, calendar events, and SSE
  event history.
- Read-only internal access to group context and offer search, protected by
  `BACKEND_TOOL_TOKEN` and required `X-Correlation-ID`.
- Agent Service run creation, SSE consumption, cancellation, semantic event normalization, and
  controlled timeout/unavailable errors. Each run stores the backend and agent run IDs, agent
  thread ID, agent stream URL, session, user, group, status, and correlation ID.
- Contract A client coverage for run create/stream/status/cancel, thread state, health, and service
  info. Protected calls send the service token explicitly; health does not. Agent-provided stream
  URLs must remain on the configured Agent Service origin and expected run stream path.
- Validation and hydration of every agent-proposed draft before persistence.
- Backend-owned UUIDs for persisted messages. Optional Agent Service message IDs are retained in a
  private `agent_message_id` column for correlation and never become database primary keys or
  frontend message IDs.
- Russian user-facing messages by default, with a basic `en-US` fallback.

## Persistence and seed data

SQLAlchemy 2 and Alembic manage the database selected by `DATABASE_URL`; SQLite is the MVP default.
`alembic upgrade head` is required before startup. Runtime never creates schema objects. Tests may
use `Base.metadata.create_all` for isolated temporary databases.

Startup transactionally reconciles flights, hotels, tours, travelers, preferences, and six
scenario groups from `data/travelers/`. It restores missing rows, corrects seed-owned fields, and
removes duplicate or stale seeded members/preferences without modifying user-created groups.
Scenario groups remain internal-only. User-created groups are private and use UUIDs.

All environment variables listed in `.env.example` are required. There are no built-in JWT or
service-token defaults.

## Streaming

Each backend run owns a persistent ordered event log. Frontend SSE replays events after
`Last-Event-ID` and closes after a terminal run status. Stream tickets are stored only as SHA-256
hashes, expire before first use, and receive a short reconnect lease after consumption.

Agent `ready` events are not forwarded directly. The backend loads referenced offers, recalculates
cost, applies hard constraints, writes the plan/map/calendar atomically, and only then emits
frontend `plan_status=ready`.

Every Agent Service event is checked for a supported semantic name, required fields, and matching
`agent_run_id`. `observability` is dropped. Conflict, escalation, plan-error, and run-error text is
localized by the backend rather than forwarding arbitrary agent text. The emitted frontend event
vocabulary is limited to the seven event types frozen in `api/openapi.yaml`.

Agent HTTP calls and SSE reads execute without an open SQLAlchemy session. Run payload loading,
agent mapping, each semantic event, terminal-state handling, and failure handling use separate
short-lived transactions while preserving sequential event ordering.

## Security and verification

Request logging records no bodies, query strings, authorization headers, passwords, refresh
tokens, or stream tickets. Sensitive token inputs have bounded request schemas, and service-token
comparison is constant-time.

Frontend HTTP errors are restricted to the frozen `api/openapi.yaml` enum. Backend-only
`timeout`/`agent_unavailable` failures are normalized to HTTP 500 `internal`; persisted SSE errors
retain their more specific machine-readable code.

The automated suite verifies route registration and authentication boundaries, resource ownership,
refresh rotation/replay, ticket hashing/scope/replay/expiry, persisted SSE reconnect, Contract A
error handling, event normalization, plan persistence gating, deterministic seed import, read-only
internal calls, business constraints, localization fallback, migration upgrades, process-isolated
test databases, and placeholder-only example secrets.

## Development

```bash
cd backend
uv python install 3.13.7
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Configuration is documented in `.env.example`; tests supply settings without real secrets.
