# Backend ↔ Agent Service Interface — Design

- **Date:** 2026-06-14
- **Status:** Approved (design); ready to freeze as OpenAPI contracts
- **Branch:** `agent-ms` (off `master`)
- **Deliverable:** two OpenAPI 3.1 ("Swagger") documents that freeze the backend↔agent interface so
  the backend and agent teams can develop independently.

## 1. Context

Final project of the course «Промышленная разработка агентов»: a travel-planning agent. The
frontend↔backend contract is already frozen ([`api/openapi.yaml`](../../../api/openapi.yaml)). This
document defines the **inner** boundary: how the **backend** drives the **agent**, now split into a
separate microservice.

The architecture follows the project's own `микросервис.md` note: the backend is a **BFF** that owns
all business data and access control, and the **agent service** is a LangGraph runtime that reasons,
retrieves (RAG), calls the LLM, and streams execution events. The agent never talks to the frontend
and never owns business data — it *proposes*, the backend *persists*.

Two architecture decisions (confirmed against `микросервис.md`) shape this contract:

- **Stateful agent (LangGraph-native).** The agent owns conversation **threads/checkpoints**. The
  backend stores only a `thread_id ↔ session` mapping and sends just the *new turn* each run.
- **Variant B data access.** The agent owns RAG/Chroma but pulls **business data** (group context,
  flight/hotel/tour offers, plan validation) from a **Backend Internal Tool API**. The backend stays
  the single owner of the business DB and access control.

## 2. Boundary & responsibilities

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

| Component | Owns |
|---|---|
| **Backend API (BFF)** | users, sessions, plans, groups, business DB, access control, persistence, proxying agent events to the frontend |
| **Agent Service** | LangGraph graph, thread state/checkpoints, prompts, reasoning, LLM calls, RAG/Chroma, run event stream |
| **Backend Internal Tool API** | read access to business data (group context, offers) + plan validation, exposed to the agent |

Two contracts are frozen here:

- **Contract A — Backend → Agent Service** (`/v1/*`): start/stream/cancel/inspect runs.
- **Contract B — Agent → Backend Internal Tool API** (`/internal/*`): read business data + validate.

## 3. Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent state | **Stateful LangGraph threads** | Native to LangGraph; backend sends only the new turn + `thread_id`. |
| Data access | **Variant B** (agent → backend internal tools) | Backend stays owner of business data + access control; agent is a thin, swappable executor. |
| Run model | **Two-call**: `POST /v1/runs` → `stream_url`, then `GET …/stream` | Reconnectable, pollable; symmetric with the frontend contract. |
| Run transport | **SSE** (`text/event-stream`) | Live progress for a slow LLM; `EventSource`-style, reconnect via `Last-Event-ID`. |
| Event vocabulary | **Stable semantic events** + one optional `observability` event | Frozen contract survives graph/impl changes; raw LangGraph `node_*` events stay optional. |
| Persistence | **Agent proposes, backend disposes** | Agent emits a `plan` (draft) over SSE; the backend validates rights/rules and persists. Contract B is read-only. |
| Inter-service auth | **Shared service tokens** (Bearer), private network | Simple to freeze; optional scopes `run:create|read|cancel`. |
| Correlation | `X-Correlation-ID` + `external_run_id ↔ agent_run_id` | One id threaded through frontend → backend → agent → tracing. |
| API version | OpenAPI **3.1**, base paths `/v1` (agent) and `/internal` (backend tools) | JSON-Schema-aligned; describes `text/event-stream`. |
| Money / ids / time | integer `*_rub`; opaque string ids; RFC 3339 UTC; flight times local `HH:MM` | Same conventions as the frontend contract & dataset. |

## 4. Contract A — Agent Service API (`/v1`)

```
POST /v1/runs
  {
    external_run_id,        // backend's run id — idempotency + correlation
    correlation_id,         // threaded through to tracing
    session_id, user_id,    // agent trusts the backend, not user_id, for authz
    thread_id?,             // omit → new thread; agent returns it (STATEFUL)
    group_id?, active_plan_id?,
    mode,                   // new_trip | modify | answer | qa
    message?,               // new_trip / qa: the new user turn only (thread holds history)
    answer?,                // mode=answer: { in_reply_to_question_id, selected_option_ids?, freeform? }
    route_edits?,           // mode=modify: { add:[{name,kind?,lat?,lng?,after_point_id?}], remove:[id], note? }
    locale?, metadata?
  }
  → 202 { agent_run_id, thread_id, status:"started", stream_url }

GET  /v1/runs/{agent_run_id}/stream     // SSE; Bearer header (server-to-server); Last-Event-ID reconnect
GET  /v1/runs/{agent_run_id}            // status snapshot
POST /v1/runs/{agent_run_id}/cancel     // 202 { status:"cancelling" }
GET  /v1/threads/{thread_id}/state      // debug/demo: AgentState snapshot (stateful)
GET  /v1/health                         // liveness/readiness (no auth)
GET  /v1/info                           // { service, version, model, graph_version, capabilities }
```

Because the agent is **stateful**, the backend sends only the new turn + `thread_id`; the agent loads
thread state. A new conversation omits `thread_id`; the agent mints one and returns it on the run.

**SSE events** (every event carries an `id` for `Last-Event-ID`; the stream closes on a terminal
`run_status`):

```
run_status          { agent_run_id, status: started|running|completed|cancelled|error, outcome? }
message_delta       { agent_run_id, message_id, delta }          // streamed assistant text
message             { agent_run_id, message: {id, role:"assistant", content} }
clarifying_question { agent_run_id, question: {id, text, options:[{id,label}], allow_freeform} }
plan_status         { agent_run_id, status: building|ready|error, error? }
plan                { agent_run_id, plan: DraftPlan }            // recommendation → backend persists
constraints_conflict{ agent_run_id, message, suggested_relaxations:[string] }   // rejection
escalation          { agent_run_id, reason, message }           // mandatory-escalation scenarios
observability       { agent_run_id, kind: node_started|node_finished|tool_call|tool_result|tool_error,
                      node?, tool?, recoverable?, summary?, ms? } // OPTIONAL — backend may log, need not forward
error               { agent_run_id, error: {code, message, recoverable?} }

outcome ∈ recommendation | clarification | constraints_conflict | escalation   // on terminal run_status

DraftPlan = { destination?, start_date?, end_date?,
              selections: { flight_id?, hotel_id?, tour_id? },  // ids; backend hydrates full details
              estimated_total_rub?, decision_rationale?,
              map_points:[{name,kind,lat,lng,order,note?}],
              calendar_events:[{type,title,start,end?,location?,ref_id?,notes?}],
              warnings?:[string] }
```

Raw LangGraph events stay **out of the frozen semantic set** and ride on the optional `observability`
event, so the agent team can change the graph without breaking the contract. The backend normalizes
semantic events into the frontend vocabulary it already exposes.

**Run lifecycle**

1. Backend `POST /v1/runs` with the new turn → `202 { agent_run_id, thread_id, stream_url }`.
2. Backend opens `GET /v1/runs/{id}/stream` and forwards normalized events to the frontend's SSE.
3. The agent reasons, pulling business data via Contract B, and emits one of the four outcomes.
4. On a `plan` event the backend validates + persists; the terminal `run_status` carries the `outcome`.

## 5. Contract B — Backend Internal Tool API (`/internal`)

Read access to business data + plan validation. **No writes** — the agent proposes the plan over the
Contract A stream; the backend persists.

```
GET  /internal/groups/{group_id}/context
   → { group_id, origin_city?, destination?, start_date?, end_date?, budget_rub?,
       members:[{traveler_id, age?, citizenship?, home_airport?, role_in_group?,
                 loyalty_program?, preferences:[{type,value,comment?}], notes?}],
       history_summary? }

POST /internal/flights/search  { origin, destination, start_date?, end_date?,
       passengers_count?, required_baggage?, max_stops?, avoid_night_arrival?, budget_rub? }
   → { items:[FlightOffer] }

POST /internal/hotels/search   { destination, start_date?, end_date?, nights?, guests_count?,
       breakfast_required?, free_cancellation_preferred?, min_stars?, budget_per_night_rub? }
   → { items:[HotelOffer] }

POST /internal/tours/search    { destination, start_date?, end_date?, pax?, budget_rub?,
       includes_flight?, includes_transfer? }
   → { items:[TourOffer] }

POST /internal/plans/validate  { group_id, plan:{flight_id?,hotel_id?,tour_id?,total_cost_rub?},
       constraints:{ budget_rub?, avoid_night_flights?, required_baggage?, … } }
   → { valid, hard_violations:[{code,message}], soft_warnings:[string], budget_left_rub? }

FlightOffer = { flight_id, origin_city, destination, price_rub, baggage_included, stops,
                departure_time, arrival_time, fare_type, notes? }   // flights.csv
HotelOffer  = { hotel_id, destination, stars, price_per_night_rub, breakfast_included,
                free_cancellation, rating, notes? }                 // hotels.csv
TourOffer   = { tour_id, destination, total_price_rub, includes_flight, includes_transfer,
                hotel_id?, notes? }                                  // tours.csv
```

Offer schemas mirror `data/travelers/*.csv` columns directly so the backend maps straight from its
rows. Group context mirrors `travel_groups.csv` + `travelers.csv` + `traveler_preferences.csv`.

## 6. Shared conventions

- **Auth:** two service tokens — Contract A `Bearer <AGENT_SERVICE_TOKEN>` (backend → agent), Contract
  B `Bearer <BACKEND_TOOL_TOKEN>` (agent → backend), services on a private network. Documented
  optional scopes `run:create|read|cancel`. `/v1/health` requires no auth. The agent trusts the
  backend's identity, never a raw `user_id`.
- **Correlation:** `X-Correlation-ID` required on every call; the backend owns the
  `external_run_id ↔ agent_run_id` and `session_id ↔ thread_id` mappings; the id is threaded to
  tracing (e.g. Langfuse) inside the agent service.
- **Error envelope** (every non-2xx): `{ "error": { "code", "message", "details"?, "recoverable"? } }`.
  | code | HTTP | meaning |
  |---|---|---|
  | `validation_error` | 422 | malformed/invalid body or params |
  | `unauthorized` | 401 | missing/invalid service token |
  | `forbidden` | 403 | token lacks the required scope |
  | `not_found` | 404 | unknown run/thread/group |
  | `conflict` | 409 | e.g. cancel of a finished run |
  | `rate_limited` | 429 | too many requests |
  | `agent_unavailable` | 502 | agent/LLM upstream failure |
  | `timeout` | 504 | upstream timeout |
  | `internal` | 500 | unexpected server error |
  Mid-stream failures use the SSE `error` event (and `observability:tool_error` for recoverable tool
  failures).
- **Money / ids / time:** integer `*_rub`; opaque string ids; RFC 3339 UTC; flight times local
  `HH:MM` — identical to the frontend contract.

## 7. Deviations from `микросервис.md` (deliberate)

1. **No agent-side plan save (`/internal/plans/drafts` dropped).** The agent proposes via the SSE
   `plan` event; the backend persists. Honors the doc's own "agent proposes, backend disposes" (§12)
   and keeps Contract B read-only/safer.
2. **Raw LangGraph events demoted** to one optional `observability` event so the frozen contract
   survives graph changes.
3. **Booking / `permissions{can_book}` dropped** — out of scope for this project (YAGNI).
4. **No re-definition of `/api/chat`** — the frontend↔backend API stays the already-frozen
   `api/openapi.yaml`.

## 8. Deliverables & placement

Per `AGENTS.md` (each module owns a `SPECIFICATION.md` referenced from the root):

- `agent-service/openapi.yaml` — Contract A (Agent Service API), OpenAPI 3.1.
- `agent-service/internal-tools-openapi.yaml` — Contract B (Backend Internal Tool API), OpenAPI 3.1.
- `agent-service/SPECIFICATION.md` — the backend↔agent boundary: both contracts, conventions, data
  mapping, run sequence.
- Root `SPECIFICATION.md` — updated to index the new module.
- This design doc lives at `docs/superpowers/specs/2026-06-14-backend-agent-api-design.md`.

## 9. Open items / future work

- MVP shortcut: start the agent as an in-process module inside the backend, then split it out behind
  this same contract (the doc's §19 pragmatic note).
- mTLS / service-to-service JWT with scopes — upgrade from static tokens when leaving the prototype.
- Plan versioning/history and `eval/*` + `debug/*` ops endpoints — separate specs.
