# API Module — Specification

**Status:** Frozen contract; implemented by `backend/` and consumed (typed) by `frontend/` via `openapi-typescript`.
**Artifact:** [`api/openapi.yaml`](./openapi.yaml) — OpenAPI 3.1 ("Swagger"), validated with
`@redocly/cli lint`.
**Design rationale:** [`docs/superpowers/specs/2026-06-13-travel-agent-api-design.md`](../docs/superpowers/specs/2026-06-13-travel-agent-api-design.md).

This module owns the **HTTP + SSE contract** between the Vue 3 chat frontend and the
travel-planning agent backend. It is the hand-off artifact other team members implement against;
the implementation lives in `backend/`, not in this contract-only directory.

## 1. Scope

**In scope (v1, frontend-facing):** auth, chat/run with SSE streaming, sessions (chat history),
groups (travel-party context), plans (route) with map and calendar.

**Out of scope (separate specs):** `eval/*` and `debug/*` ops endpoints; plan versioning/history;
the agent's internal tools/prompts and the SQLite schema (owned by the backend).

## 2. Architecture

- **Resource REST + async run model.** A chat message creates a **run** (one agent turn). The run's
  events are delivered over **Server-Sent Events**; sessions, groups, and plans are addressable
  resources that survive reloads and deep-links.
- **Real-time transport — SSE** (`text/event-stream`), one typed event stream per run. Unidirectional
  and `EventSource`-friendly; reconnect via the `Last-Event-ID` header. Route edits are ordinary
  POSTs, so no WebSocket is needed.
- **Base path** `/api/v1`. **OpenAPI 3.1** (JSON-Schema-aligned; able to describe `text/event-stream`).

### Run lifecycle

1. `POST /chat` → `202 { run_id, session_id }` (a new session is created when `session_id` is omitted).
2. `POST /chat/{run_id}/stream-ticket` → a short-lived, single-use ticket.
3. `GET /chat/{run_id}/stream?ticket=…` → SSE: assistant text, clarifying questions, map snapshots,
   and a `plan_status` that goes `building → ready | error`.
4. While `plan_status != ready`, the map is **read-only** (`editable = false`).
5. To revise: `POST /plans/{id}/modify` (batch add/remove points + optional note) → `202 { run_id }`;
   the plan flips back to `building` and the agent rebuilds, streaming on the **new** run.

**Clarifying questions** are closed (mutually exclusive options) with an optional freeform field.
They are answered by reusing `POST /chat` with
`{ in_reply_to_question_id, selected_option_ids?, freeform? }` — no separate endpoint.
Persisted answer history may also include backend-resolved `selected_option_labels` so clients and
downstream services can display/read the selected option text without treating opaque option ids as
user language.

## 3. Authentication

- **Email + password**, JWT **access** (~15 min, claim `sub = user_id`) + **refresh** (~30 d, rotated
  on use). HTTP `Bearer` on every endpoint except `register` / `login` / `refresh`.
- **SSE auth — one-time stream ticket.** Browser `EventSource` cannot set an `Authorization` header,
  so the stream is authorized by a short-lived (~60 s), single-use, run-scoped ticket minted via
  `POST /chat/{run_id}/stream-ticket`. This keeps the long-lived JWT out of URLs, logs, and history.

## 4. Endpoint surface

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` |
| Chat / Run | `POST /chat`, `POST /chat/{run_id}/stream-ticket`, `GET /chat/{run_id}/stream`, `POST /chat/{run_id}/cancel` |
| Sessions | `GET /sessions`, `GET /sessions/{session_id}` |
| Groups | `GET/POST /groups`, `GET /groups/{id}`, `GET /groups/{id}/members`, `GET /groups/{id}/preferences`, `GET /groups/{id}/plans` |
| Plans | `GET /plans` (all of the user's plans, group-less included), `GET /plans/{id}`, `POST /plans/{id}/accept`, `POST /plans/{id}/reject`, `POST /plans/{id}/modify`, `GET /plans/{id}/map`, `GET /plans/{id}/calendar` |

### SSE events (`event:` name → `data:` schema)

| `event:` | `data:` schema | Purpose |
|---|---|---|
| `run_status` | `RunStatusEvent` | `started \| running \| completed \| cancelled \| error` (terminal closes stream) |
| `message_delta` | `MessageDeltaEvent` | streamed assistant text chunk |
| `message` | `MessageEvent` | a complete assistant message |
| `clarifying_question` | `ClarifyingQuestionEvent` | closed question + options + `allow_freeform` |
| `plan_status` | `PlanStatusEvent` | `building \| ready \| error` (gates map editing) |
| `map` | `MapEvent` | full map snapshot of visited settlements |
| `error` | `ErrorEvent` | run-level error |

`MapPoint` keeps its original required route fields and may additionally carry validated,
Agent-provided place-card content such as visit timing, cost, summary, facts, tips, food details,
calendar linkage, provenance, and confidence. These additions are optional and backward-compatible.
`description` is a deprecated compatibility alias for the preferred `summary` field.

## 5. Object model

```
User ──< Session (a "chat") ──< Run (one agent turn) ──< Message
                              └─> Plan (the route) ──> MapPoint[]  +  CalendarEvent[]
Group (reusable travel-party / trip context) ──< Member ──< Preference
A Run may be linked to a Group (the selected "context") and produces/updates a Plan.
```

A Group's trip fields (`origin_city` / `destination` / dates / `budget_rub`) are **optional**, so a
group can be either a pure reusable party or a fully-specified request.

## 6. Data-model mapping

API schemas mirror the dataset columns so the backend maps straight from SQLite/CSV rows.

| API schema | Source |
|---|---|
| `FlightSel` | `data/travelers/flights.csv` |
| `HotelSel` | `data/travelers/hotels.csv` (+ derived `nights`) |
| `TourSel` | `data/travelers/tours.csv` |
| `Group` (trip fields) | `data/travelers/travel_groups.csv` |
| `Member` | `data/travelers/travelers.csv` + `group_members.csv` (`role_in_group`) |
| `Preference` | `data/travelers/traveler_preferences.csv` |
| `Plan.decision_rationale`, `Plan.status`, `HotelSel.nights` | `data/reference/{flight,hotel}_recommendations.csv` |
| `MapPoint` rich place content | Agent Service draft, validated and persisted by the backend |

**Type notes.** Money fields are integer `*_rub` (whole rubles). The CSV `*_included` /
`free_cancellation` / `includes_*` columns are stored as `0`/`1` but exposed as JSON **booleans**.
Flight `departure_time` / `arrival_time` are local `HH:MM` time-of-day strings (as stored); calendar
event `start` / `end` are RFC 3339 datetimes.

Rich map content is plain text and structured lists, not trusted HTML. Missing optional content is
omitted rather than generated by the backend. Frontend behavior and Agent Service output
expectations are documented in
[`docs/FRONTEND_EXPECTATIONS.md`](../docs/FRONTEND_EXPECTATIONS.md) and
[`docs/AGENT_ROUTE_CONTENT_EXPECTATIONS.md`](../docs/AGENT_ROUTE_CONTENT_EXPECTATIONS.md).

## 7. Conventions

- **Pagination:** `?limit=20&offset=0` → `{ items, total, limit, offset }`.
- **Error envelope** (every non-2xx): `{ "error": { "code", "message", "details"? } }`.
  Codes: `validation_error` (422), `unauthorized` / `token_expired` (401), `forbidden` (403),
  `not_found` (404), `conflict` (409), `plan_not_ready` (409), `rate_limited` (429), `internal` (500).
- **IDs:** opaque strings — UUIDs for new entities; seeded groups keep `G-0001`-style ids.
- **Timestamps:** RFC 3339 UTC (except flight times, see §6).

## 8. Working with the artifact

```bash
# Validate the contract
npx @redocly/cli lint api/openapi.yaml

# Preview interactive docs (Redoc)
npx @redocly/cli preview-docs api/openapi.yaml
# or import api/openapi.yaml into editor.swagger.io / Swagger UI
```

Generators (e.g. `openapi-typescript`, `orval`) can produce the frontend client types from this file.

## 9. Open items

- `eval/*` and `debug/*` ops endpoints — separate spec.
- Plan versioning/history (revision list per plan) — out of scope for v1; the current model keeps a
  single mutable plan per build chain.
