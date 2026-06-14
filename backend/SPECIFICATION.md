# Backend Service Specification

**Status:** Implemented MVP.

The `backend/` module is the FastAPI BFF between the Vue frontend and the external Agent Service.
It implements the frozen frontend contract in `api/openapi.yaml` and the Backend Internal Tool API
in `agent-service/internal-tools-openapi.yaml`. The Agent Service itself is not implemented here.

## Responsibilities

- JWT access authentication, rotating hashed refresh tokens, and user ownership checks.
- Persistent users, sessions, runs, messages, groups, plans, map points, calendar events, and SSE
  event history.
- Read-only internal access to group context and offer search, protected by
  `BACKEND_TOOL_TOKEN` and required `X-Correlation-ID`.
- Agent Service run creation, SSE consumption, cancellation, semantic event normalization, and
  controlled timeout/unavailable errors.
- Validation and hydration of every agent-proposed draft before persistence.
- Russian user-facing messages by default, with a basic `en-US` fallback.

## Persistence and seed data

SQLAlchemy 2 and Alembic manage the database selected by `DATABASE_URL`; SQLite is the MVP default.
Startup idempotently imports flights, hotels, tours, travelers, preferences, and six scenario groups
from `data/travelers/`. Scenario groups are internal-only. User-created groups are private and use
UUIDs.

## Streaming

Each backend run owns a persistent ordered event log. Frontend SSE replays events after
`Last-Event-ID` and closes after a terminal run status. Stream tickets are stored only as SHA-256
hashes, expire before first use, and receive a short reconnect lease after consumption.

Agent `ready` events are not forwarded directly. The backend loads referenced offers, recalculates
cost, applies hard constraints, writes the plan/map/calendar atomically, and only then emits
frontend `plan_status=ready`.

## Development

```bash
cd backend
uv python install 3.13.7
uv sync
uv run alembic upgrade head
uv run uvicorn travel_backend.main:app --reload
uv run pytest
```

Configuration is documented in `.env.example`; tests supply settings without real secrets.

