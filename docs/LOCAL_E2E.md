# Local end-to-end runbook

How to run the whole system (frontend + backend BFF + Agent Service) on one machine and exercise a
real chat → plan run against GigaChat. Every command below was verified on macOS (Apple Silicon),
Python 3.13 via `uv`, Node 26 / pnpm 11.

## 0. Prerequisites

- `uv` (Python), `pnpm` + Node 20+ (frontend).
- Valid **GigaChat** credentials (the `GIGACHAT_CREDENTIALS` Authorization key, scope
  `GIGACHAT_API_PERS`). The Agent Service is the only component that calls an LLM.
- Network egress to `ngw.devices.sberbank.ru:9443` (OAuth) and `gigachat.devices.sberbank.ru` (API).

## 1. Secrets / env files

Three local `.env` files are **gitignored**. The two shared service tokens must be identical across
backend and agent-service.

- `backend/.env` — from `backend/.env.example`; set `JWT_SECRET`, `BACKEND_TOOL_TOKEN`,
  `AGENT_SERVICE_TOKEN`. Keep `AGENT_SERVICE_URL=http://localhost:8001`,
  `CORS_ORIGINS=http://localhost:5173,http://localhost:4173`.
- `agent-service/.env` — from `agent-service/.env.example`; set the **same** `AGENT_SERVICE_TOKEN`
  and `BACKEND_TOOL_TOKEN`, `BACKEND_BASE_URL=http://localhost:8000`, and `GIGACHAT_CREDENTIALS`.
- `.env` (repo root) — used only by the RAG index builder: `GIGACHAT_CREDENTIALS`, `GIGACHAT_SCOPE`,
  `GIGACHAT_MODEL`.

## 2. Build the RAG policy index (once)

The Agent Service's reasoning core needs a Chroma index of the policy docs at
`data/indexes/policy_chroma` (built from `data/documents/*.md`). The agent's first run **errors**
without it.

```bash
# uses GigaChat embeddings; reads repo-root .env
agent-service/.venv/bin/python agent/scripts/build_policy_index.py
```

(Run `cd agent-service && uv sync --extra llm` first if the venv does not exist — see step 4.)

## 3. Backend (port 8000)

```bash
cd backend
uv sync                       # provisions Python 3.13 + deps (incl. greenlet for async SQLAlchemy)
uv run alembic upgrade head   # REQUIRED before first start — no runtime create_all
# load .env and serve; seeds synthetic inventory + scenario groups on startup
set -a; . ./.env; set +a
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health: `curl http://127.0.0.1:8000/health` → `200`. Tests: `uv run pytest -q` → 93 passed.

## 4. Agent Service (port 8001)

```bash
cd agent-service
uv sync --extra llm           # base service + reasoning core (langchain/langgraph/gigachat/chroma)
set -a; . ./.env; set +a
uv run uvicorn agent_service.main:app --host 127.0.0.1 --port 8001
```

Health: `curl http://127.0.0.1:8001/v1/health` → `200`. Offline smoke (no creds needed):
`.venv/bin/python tests/smoke.py` → 16 passed.

## 5. Frontend (port 5173 dev, or 4173 preview)

The frontend ships with MSW mocks ON by default. To point it at the **real** backend:

```bash
cd frontend
pnpm install
# dev server against the real backend (mocks off):
VITE_USE_MOCKS=false VITE_API_BASE=http://localhost:8000/api/v1 pnpm dev
#   -> http://localhost:5173  (already in backend CORS_ORIGINS)

# OR a production build + preview (mocks are always off in a build):
VITE_API_BASE=http://localhost:8000/api/v1 pnpm build && pnpm preview --port 5173
```

See `frontend/.env.example`. Leaving `VITE_USE_MOCKS` unset keeps the default mock-backed dev UX.

## 6. Smoke-test the chain without the UI

```
POST /api/v1/auth/register {name,email,password}
POST /api/v1/auth/login    {email,password}            -> access_token
POST /api/v1/chat          {message[, group_id]}        -> {run_id, session_id}   (202)
POST /api/v1/chat/{run_id}/stream-ticket                -> {ticket}               (60s TTL)
GET  /api/v1/chat/{run_id}/stream?ticket=...            -> SSE: run_status, message,
                                                           clarifying_question, plan_status, plan
```

A clarifying question ends the run turn; answer it with another `POST /api/v1/chat`
`{session_id, in_reply_to_question_id, freeform | selected_option_ids}` to continue the thread.
Agent outcomes are one of: `recommendation` (a ready plan with map points), `clarification`,
`constraints_conflict`, or `escalation`.

## Call graph

```
frontend :5173 ──JWT /api/v1──▶ backend :8000 ──Contract A (AGENT_SERVICE_TOKEN) /v1──▶ agent :8001
                                     ▲                                                       │
                                     └────────── Contract B (BACKEND_TOOL_TOKEN) /internal ──┘
                                                                                        agent ──▶ GigaChat
```
