# Backend Service Specification

**Status:** Implemented and verified MVP.

The `backend/` module is the FastAPI BFF between the Vue frontend and the external Agent Service.
It implements the frozen frontend contract in `api/openapi.yaml` and the Backend Internal Tool API
in `agent-service/internal-tools-openapi.yaml`. The Agent Service itself is not implemented here.
The supported ASGI entry point is `app.main:app`; `app/` is a two-file ASGI facade, while all
runtime implementation lives in the installable `travel_backend` package.

## Responsibilities

- JWT access authentication, atomically rotating hashed refresh tokens, and user ownership checks.
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
- Strict validation and persistence of optional Agent-provided route timing, cost, calendar links,
  provenance, and rich place-card content. The backend never generates missing place intelligence.
- Backend-owned UUIDs for persisted messages. Optional Agent Service message IDs are retained in a
  private `agent_message_id` column for correlation and never become database primary keys or
  frontend message IDs. Streamed deltas and the corresponding final message share the same
  backend-owned message ID.
- Clarifying-question answers store stable selected option IDs and, when the referenced persisted
  question is available, backend-resolved selected option labels. The labels are used for user-visible
  answer content and forwarded to the Agent Service so opaque IDs are not interpreted as language.
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
hashes, expire before first use, receive a short reconnect lease after consumption, and are
validated against the owning user recorded on the run before they are consumed. First consumption
uses a conditional database update, so concurrent initial connections cannot both redeem a ticket.
Run event numbers are allocated through an atomic per-run database counter rather than `max + 1`.

Agent `ready` events are not forwarded directly. The backend loads referenced offers, recalculates
cost, applies hard constraints, writes the plan/map/calendar atomically, and only then emits
frontend `plan_status=ready`. Group context for agent reasoning, draft validation, and new-plan
ownership is taken from the per-run group snapshot (`Run.group_id`) captured when the run was
created, not from the session's current group, so re-pointing a session at a different group does
not retroactively re-target an older run. Stay-length pricing floors the trip to at least one night
for same-day groups, and the serialized hotel `nights` applies the same floor so the displayed
nights and recalculated total stay consistent. A run **without** a group (free-form chat plans, the
common case) still validates and persists: `validate_selection` tolerates `group=None` (it checks the
offers exist and is skipped destination/preference checks that need a group), and `persist_draft`
passes the draft's own trip dates as a `nights_override` so the hotel subtotal reflects the real trip
length instead of defaulting to a single night. The agent-side recommendation gate is relaxed for
group-less runs (it cannot call Contract B `validate` without a `group_id`), but the backend remains
the authority — an agent `ready` is still ignored until the draft passes this validation and is
persisted.

Map points keep normalized route coordinates and ordering in columns, with validated optional
place-card attributes stored as JSON. Public map fields are flat and backward-compatible.
`description` is a legacy alias of `summary`. Private Agent calendar correlation values are
resolved to backend-owned calendar event IDs and are never returned.

Every Agent Service event is checked for a supported semantic name, required fields, and matching
`agent_run_id`. `observability` is dropped. Conflict, escalation, plan-error, and run-error text is
localized by the backend rather than forwarding arbitrary agent text. The emitted frontend event
vocabulary is limited to the seven event types frozen in `api/openapi.yaml`.
An Agent `error` SSE event immediately persists a terminal backend run state, emits both `error` and
terminal `run_status:error`, and ignores any later events for that run. If a modify/rebuild run asks a
clarifying question or otherwise completes without a replacement recommendation, the previously active
plan is restored to `ready` and a `plan_status:ready` event is emitted so the UI is not left in a
permanent rebuilding state.

Agent route content rejects unknown fields, invalid types, invalid confidence values, duplicate
orders/references, unsafe datetime forms, and oversized text/list/aggregate payloads. Content is
returned as plain strings and lists; the backend does not treat it as HTML or verify its factual
truth. Persisted JSON details are filtered through the frontend contract's public field allowlist
when serialized. Individual Agent SSE event frames are bounded to 1.1 MB, and private Agent message
IDs are limited to the existing 200-character storage boundary. Clarifying questions are rebuilt
from their frozen public fields before persistence and relay. The current runtime does not support
a `route_preview` event.

Agent HTTP calls and SSE reads execute without an open SQLAlchemy session. Run payload loading,
agent mapping, each semantic event, terminal-state handling, and failure handling use separate
short-lived transactions while preserving sequential event ordering. Agent cancellation also
releases its request database session before committing the local terminal state in a short-lived
transaction, then calls the upstream Agent Service, preventing later Agent events from being
persisted. If a run becomes terminal (for example, cancelled) in the window between creating the
upstream agent run and claiming its local mapping, the just-created agent run is cancelled upstream
so it is not left orphaned.

Backend-generated run failure messages, including plan failure events, use the locale captured
when the run was created. Russian remains the default and `en-US` is supported.

## Security and verification

Request logging records no bodies, query strings, authorization headers, passwords, refresh
tokens, or stream tickets. Sensitive token inputs have bounded request schemas, and service-token
comparison is constant-time. Credentialed CORS requires an explicit trusted-origin allowlist and
permits only the public API's `GET` and `POST` methods.

Frontend HTTP errors are restricted to the frozen `api/openapi.yaml` enum. Backend-only
`timeout`/`agent_unavailable` failures are normalized to HTTP 500 `internal`; persisted SSE errors
retain their more specific machine-readable code.
The in-process rate limiter sweeps expired buckets globally on each check so one-off keys cannot
accumulate indefinitely when traffic shifts to different users or routes.

The automated suite verifies route registration and authentication boundaries, resource ownership,
refresh rotation/replay, ticket hashing/scope/replay/expiry, persisted SSE reconnect, Contract A
error handling, event normalization, plan persistence gating, deterministic seed import, read-only
internal calls, business constraints, localization fallback, migration upgrades, process-isolated
test databases, rich route-content validation and serialization, private calendar-link resolution,
placeholder-only example secrets, concurrent refresh/ticket/event behavior, reverse-order
independence, and two-worker pytest execution.

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
