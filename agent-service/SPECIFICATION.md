# Agent Service Module — Specification

**Status:** Contracts defined (design approved). **Contract A is implemented** as the FastAPI service
in this directory (`src/agent_service/`, see [`README.md`](./README.md)) — it serves runs+SSE and
validates recommendation drafts through Contract B. The reasoning core is the Final agent graph
([`agent/baselines/final_agent.py`](../agent/baselines/final_agent.py)); LLM credentials and the
policy index are required for real runs.
**Artifacts:**
- [`agent-service/openapi.yaml`](./openapi.yaml) — **Contract A** (Backend → Agent Service), OpenAPI 3.1.
- [`agent-service/internal-tools-openapi.yaml`](./internal-tools-openapi.yaml) — **Contract B**
  (Agent → Backend Internal Tool API), OpenAPI 3.1.

**Design rationale:** [`docs/superpowers/specs/2026-06-14-backend-agent-api-design.md`](../docs/superpowers/specs/2026-06-14-backend-agent-api-design.md).
Both files validate with `@redocly/cli lint`.

This module freezes and implements the **backend↔agent interface** so the backend and agent teams can
develop independently. Contract B remains implemented by the backend; this service consumes it.

## 1. Boundary

```
Frontend ──REST/SSE──▶ Backend API (BFF)  ◀── owns: users, sessions, plans, groups,
   (frozen: api/openapi.yaml)  │   ▲              business DB, access control, persistence
                               │   │
        Contract A: POST /v1/runs, GET stream, status, cancel  (SSE: semantic events)
                               ▼   │
                         Agent Service ── owns: LangGraph graph, thread state/checkpoints,
                               │   ▲          prompts, reasoning, LLM, RAG/Chroma
        Contract B: agent calls /internal/* for business data + validation
                               ▼   │
                      Backend Internal Tool API ──▶ business DB (offers, groups)
```

The frontend never calls the agent. The agent **proposes** a draft plan; the backend **validates and
persists** (via the already-frozen plan endpoints in [`api/openapi.yaml`](../api/openapi.yaml)).
For clarification answers, the backend may send both stable `selected_option_ids` and resolved
`selected_option_labels`; the planner uses the labels for user text and falls back to IDs only when
labels are unavailable.

## 2. Architecture decisions

| Decision | Choice |
|---|---|
| Agent state | In-memory run/thread store for MVP; backend sends new turns with `thread_id`. Runs, threads, and per-run SSE event buffers are retained for the process lifetime (no eviction yet) so streams can be reconnected via `Last-Event-ID`; size-bounded retention and persistent LangGraph checkpoints are a follow-up. |
| Data access | Agent owns policy RAG and local experimental graph data access; recommendation drafts are validated via Backend Contract B. |
| Run model | **Two-call**: `POST /v1/runs` → `stream_url`, then `GET /v1/runs/{id}/stream` (SSE). |
| Event vocabulary | **Stable semantic events** + one optional `observability` event (raw LangGraph steps). |
| Persistence | **Agent proposes, backend disposes** — Contract B is read-only. |
| Inter-service auth | **Shared service tokens** (Bearer), private network; optional scopes. |

## 3. Contract A — Agent Service API (`/v1`)

| Endpoint | Purpose |
|---|---|
| `POST /v1/runs` | Create a run on a thread (new turn + `thread_id`); returns `agent_run_id`, `thread_id`, `stream_url`. |
| `GET /v1/runs/{agent_run_id}/stream` | SSE event stream; reconnect via `Last-Event-ID`. |
| `GET /v1/runs/{agent_run_id}` | Run status snapshot (`status`, `current_node`, `outcome`). |
| `POST /v1/runs/{agent_run_id}/cancel` | Request cooperative cancellation. |
| `GET /v1/threads/{thread_id}/state` | AgentState snapshot (debug/demo). |
| `GET /v1/health` | Liveness/readiness (no auth). |
| `GET /v1/info` | Service metadata (version, model, graph version, capabilities). |

**SSE events (`event:` name → `data:` schema):**

| `event:` | `data:` schema | Meaning |
|---|---|---|
| `run_status` | `RunStatusEvent` | lifecycle; terminal carries `outcome` |
| `message_delta` | `MessageDeltaEvent` | streamed assistant text chunk |
| `message` | `MessageEvent` | a complete assistant message |
| `clarifying_question` | `ClarifyingQuestionEvent` | closed options + `allow_freeform` |
| `plan_status` | `PlanStatusEvent` | `building \| ready \| error` |
| `plan` | `PlanEvent` | draft plan (`DraftPlan`) — backend persists |
| `constraints_conflict` | `ConstraintsConflictEvent` | rejection + `suggested_relaxations` |
| `escalation` | `EscalationEvent` | mandatory-escalation scenarios |
| `observability` | `ObservabilityEvent` | **optional** node/tool steps; backend may log, need not forward |
| `error` | `ErrorEvent` | run-level error |

`outcome ∈ recommendation | clarification | constraints_conflict | escalation`.

**Run lifecycle:** `POST /v1/runs` → open `…/stream` → Final agent graph reasons → the service maps
the graph output to Contract A semantic events. Before a `recommendation` is emitted on a run that
carries a `group_id`, the service calls `POST /internal/plans/validate`; on `valid=false` it
downgrades to `clarification`, and that gate **never fails open** (backend unreachable/errors also
downgrades). On a **group-less** run (free-form chat with no pre-selected group — the common case),
`POST /internal/plans/validate` cannot run (it requires a `group_id`), so the service forwards the
agent's recommendation, which is already grounded by the graph's deterministic feasibility
calculator. This does **not** emit an unvalidated plan to the user: the backend re-validates the
draft on the `plan` event (`validate_selection`) and **ignores `plan_status: ready` until the draft
passes validation and is persisted**, so the backend remains the sole authority over what becomes a
plan. A recommendation that carries no concrete selection is downgraded to `clarification`. On a
`plan` event the backend validates and persists; terminal `run_status` carries the `outcome`. The
backend normalizes these semantic events into the frontend vocabulary it already exposes.

**Conversation memory & group-less planning.** The Final graph is single-shot, so the service feeds
it the whole dialogue, not just the latest turn: every user turn is recorded on the thread for
**every** mode (`new_trip`/`answer`/`modify`), and the planner passes the full transcript as
`user_request` plus a user-only projection as `user_text_only` (so the graph never re-asks for facts
already given, and deterministic destination/origin matching never trips over option labels the agent
echoed in earlier questions). Without a pre-selected group the graph resolves the destination/origin
from the conversation against a fixed **destination catalogue**
([`agent/baselines/travel_catalog.py`](../agent/baselines/travel_catalog.py)); a destination that is
not in the catalogue (or a country with several catalogue cities, or a missing departure city)
produces a `clarifying_question` whose `options` list the destinations/cities the agent can actually
plan — closed options, not freeform-only.

A `message` event is emitted **only for the `info` outcome**. For every structured outcome the
backend already produces the user-facing assistant message itself (the plan-ready message for
`recommendation`, the question text for `clarification`, and the localized escalation/conflict text
for `escalation`/`constraints_conflict`), so the service no longer also emits a redundant `message` —
doing so previously made the backend persist two assistant rows for one turn (a duplicated answer
bubble, identical text for clarifications).

## 4. Contract B — Backend Internal Tool API (`/internal`)

Read-only business data + validation for the agent. **The agent never writes here.**

| Endpoint | Purpose |
|---|---|
| `GET /internal/groups/{group_id}/context` | Group trip fields + members + preferences + history summary. |
| `POST /internal/flights/search` | Flight offers matching origin/destination/constraints. |
| `POST /internal/hotels/search` | Hotel offers matching destination/dates/constraints. |
| `POST /internal/tours/search` | Package-tour offers. |
| `POST /internal/plans/validate` | Validate a candidate plan against budget + constraints; returns hard violations / soft warnings / budget left. |

## 5. Conventions

- **Auth:** Contract A `Bearer <AGENT_SERVICE_TOKEN>` (backend → agent); Contract B
  `Bearer <BACKEND_TOOL_TOKEN>` (agent → backend); private network. `/v1/health` is open. Optional
  scopes `run:create|read|cancel`. The agent trusts the backend's identity, never a raw `user_id`.
- **Correlation:** `X-Correlation-ID` required on every call; backend owns the
  `external_run_id ↔ agent_run_id` and `session_id ↔ thread_id` mappings; threaded to tracing.
- **Error envelope:** `{ "error": { "code", "message", "details"?, "recoverable"? } }`. Codes:
  `validation_error`(422), `unauthorized`(401), `forbidden`(403), `not_found`(404), `conflict`(409),
  `rate_limited`(429), `agent_unavailable`(502), `timeout`(504), `internal`(500). Mid-stream failures
  use the SSE `error` event.
- **Money / ids / time:** integer `*_rub`; opaque string ids; RFC 3339 UTC; flight times local
  `HH:MM` — identical to the frontend contract.

## 6. Data-model mapping (Contract B)

| API schema | Source |
|---|---|
| `GroupContext` (trip fields) | `data/travelers/travel_groups.csv` |
| `GroupMember` | `data/travelers/travelers.csv` + `group_members.csv` (`role_in_group`) |
| `Preference` | `data/travelers/traveler_preferences.csv` |
| `FlightOffer` | `data/travelers/flights.csv` |
| `HotelOffer` | `data/travelers/hotels.csv` |
| `TourOffer` | `data/travelers/tours.csv` |
| `ValidationResult` (rationale/violations) | `data/reference/*_recommendations.csv` |

The CSV `*_included` / `free_cancellation` 0/1 columns are exposed as JSON booleans.

## 7. Working with the artifacts

```bash
npx @redocly/cli lint agent-service/openapi.yaml
npx @redocly/cli lint agent-service/internal-tools-openapi.yaml
npx @redocly/cli preview-docs agent-service/openapi.yaml   # interactive docs
```

## 8. Open items

- Multi-turn memory is currently the full transcript threaded into a single-shot graph; persistent
  LangGraph checkpoints (below) would let the graph keep structured state across turns instead.
- The destination catalogue ([`travel_catalog.py`](../agent/baselines/travel_catalog.py)) is hardcoded
  to the seed dataset; derive it from Contract B (e.g. a `/internal/destinations` endpoint) once the
  Final graph reads offers over HTTP.
- Replace local CSV access inside the experimental Final graph with HTTP tools over Contract B.
- Persistent LangGraph checkpoints instead of the current in-memory run/thread store.
- mTLS / service-to-service JWT with scopes — upgrade from static tokens after the prototype.
- Plan versioning/history and `eval/*` + `debug/*` ops endpoints — separate specs.
