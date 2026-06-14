# Travel Backend

FastAPI backend/BFF for the travel-planning agent. The service implements the frozen
frontend-facing API under `/api/v1`, exposes the read-only Agent Service tool API under
`/internal`, persists business state in SQLite, and treats Agent Service as an external dependency.

## Requirements

- Python 3.13.7
- `uv`

Dependencies are installed only into `backend/.venv`.

## Setup

```bash
cd backend
uv python install 3.13.7
uv sync
```

Copy `.env.example` to `.env` for local development and replace every placeholder. Never commit
the resulting `.env`.

## Environment

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy async URL, normally `sqlite+aiosqlite:///./backend.db` |
| `JWT_SECRET` | Secret used to sign access JWTs |
| `ACCESS_TOKEN_TTL_MINUTES` | Access token lifetime |
| `REFRESH_TOKEN_TTL_DAYS` | Refresh token lifetime |
| `BACKEND_TOOL_TOKEN` | Bearer token accepted by `/internal/*` |
| `AGENT_SERVICE_URL` | Agent Service base URL |
| `AGENT_SERVICE_TOKEN` | Bearer token sent to Agent Service |
| `DEFAULT_LOCALE` | Default user-facing locale, `ru-RU` |
| `SUPPORTED_LOCALES` | Comma-separated locale list |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `LOG_LEVEL` | Python logging level |

Optional settings include `AGENT_CONNECT_TIMEOUT_SECONDS`,
`AGENT_READ_TIMEOUT_SECONDS`, `STREAM_TICKET_TTL_SECONDS`, and
`STREAM_RECONNECT_LEASE_SECONDS`.

## Database

```bash
uv run alembic upgrade head
```

Startup idempotently imports the synthetic inventory and internal scenario groups from `../data`.
Local database files are ignored by Git.

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Interactive documentation is available at `http://localhost:8000/docs`.

## Quality checks

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Tests use an isolated SQLite database and mocked Agent Service HTTP/SSE responses. They require no
real service token, LLM, or `.env` file.

