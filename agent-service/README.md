# Agent Service

Implements **Contract A** (`openapi.yaml`, Backend → Agent: runs + SSE) and calls **Contract B**
(`internal-tools-openapi.yaml`, Agent → Backend `/internal/*`) for business data — **Variant B**. The
reasoning core is the Final agent (`agent/baselines/final_agent.py`): specialists pick offers, a
feasibility calculator grounds the facts, and the agent decides the outcome.

## Run

```bash
cd agent-service
uv sync                      # or: pip install -e . (add ".[llm]" for the GigaChat reasoning planner)
cp .env.example .env         # set AGENT_SERVICE_TOKEN + BACKEND_TOOL_TOKEN to match the backend
PYTHONPATH=src uvicorn agent_service.main:app --host 0.0.0.0 --port 8001
```

The backend reaches us at `AGENT_SERVICE_URL` (default `http://localhost:8001`) with
`Authorization: Bearer <AGENT_SERVICE_TOKEN>`; we reach the backend's `/internal/*` at
`BACKEND_BASE_URL` with `Authorization: Bearer <BACKEND_TOOL_TOKEN>`. **The two tokens must match the
backend's env.** Both services seed from the same `data/` dataset, so offer ids line up and the
backend's `persist_draft` validation passes.

## Planner

The service uses the experimental Final agent from `../agent/baselines/final_agent.py`. It requires
`GIGACHAT_CREDENTIALS` and the policy index from `agent/scripts/build_policy_index.py`; runs fail
explicitly if the Final agent cannot be initialized.

Before emitting a `recommendation`, the service calls the backend's **`POST /internal/plans/validate`**
(Contract B) and only recommends when the backend says the plan is valid — so a recommended plan also
passes the backend's `persist_draft` validation. On a backend `valid=false` the service downgrades the
result to `clarification`.

## Endpoints (Contract A, base `/v1`)

`POST /runs` · `GET /runs/{id}/stream` (SSE) · `GET /runs/{id}` · `POST /runs/{id}/cancel` ·
`GET /threads/{id}/state` · `GET /health` (no auth) · `GET /info`.

Outcome → SSE events:

| outcome | events |
|---|---|
| recommendation | `plan_status: building` → `plan` (DraftPlan) → `plan_status: ready` → `message` → `run_status: completed` |
| clarification | `clarifying_question` → `message` → `run_status` |
| rejection | `constraints_conflict` → `message` → `run_status` (outcome `constraints_conflict`) |
| escalation | `escalation` → `message` → `run_status` |
| info | `message` → `run_status` |

## Test

```bash
.venv/bin/python agent-service/tests/smoke.py   # HTTP/SSE surface with a fake planner
```

## MVP limitations

- In-memory run/thread store (no persistence across restarts); production needs a checkpoint store.
- `Last-Event-ID` resume replays from the in-memory buffer only.
- Map-point coordinates come from a small static city lookup (`events.py`).
- Service-to-service auth is a static bearer token (matches the backend MVP).
