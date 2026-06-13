# Travel-Planning Agent — Frontend/Backend API Design

- **Date:** 2026-06-13
- **Status:** Approved (design); ready for implementation planning
- **Deliverable:** an OpenAPI 3.1 ("Swagger") document covering all frontend-facing endpoints

## 1. Context

This is the final project of the "Industrial development of agents" course: a **travel-planning
agent**. The backend works over a SQLite domain (`data/travelers/`) of travelers, groups, flights,
hotels, and tours, plus reference plans (`data/reference/`) and a Q&A eval set (`data/qa/`). The
agent picks optimal flights/hotels/tours for a travel group given budget, constraints, and
preferences, and rebuilds the plan when the user changes the inputs.

The frontend is a Vue 3 + TypeScript + Vite chat UI. Today it has only a styled input box
(`frontend/src/components/AgentChat/`) and no API client — so this contract is designed
essentially greenfield, grounded in the existing data model.

This document defines the **HTTP/SSE contract** between that frontend and the backend.

## 2. Goals & non-goals

**Goals**
- A chat with the agent: send/receive regular messages.
- The agent can ask **clarifying questions** — closed (mutually exclusive options) plus an optional
  freeform field when the options don't fit.
- The backend streams, in real time: assistant text, clarifying questions, **map points** (visited
  settlements to render), and **route build status** (`building` / `ready` / `error`).
- While the route is not `ready`, the map is **read-only**.
- The user can **correct the route**: add/remove map points and resubmit as a batch; the plan goes
  from `ready` back to `building` and the agent rebuilds with the new wishes.
- Auth: register (name, email, password), login (access + refresh JWT), refresh.
- Chat history: list of chats (short summary of the first request) + full message history of a chat.
- Travel groups: create a group describing all participants; list a user's groups; select a group as
  the chat **context** (its `group_id` is attached to the plan).
- Plans: fetch, accept, reject, modify; fetch map and calendar.

**Non-goals (excluded from this spec)**
- `eval/*` and `debug/*` ops endpoints — deferred to a separate spec later.
- The agent's internal tools/prompts and the SQLite schema itself (owned by the backend).

## 3. Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Real-time transport | **SSE** (`text/event-stream`), one typed event stream | Matches `GET /chat/{run_id}/stream`; unidirectional; reconnect via `Last-Event-ID`. Edits are ordinary POSTs, so no need for WebSockets. |
| Architecture | Resource REST + async **run** model | A chat message creates a run; the run streams events; sessions/groups/plans are addressable resources. Survives reloads and deep-links. |
| Auth | **Email + password**, JWT access + refresh | Self-contained, no email infra. |
| SSE auth | **One-time stream ticket** | Browser `EventSource` can't set an `Authorization` header; a short-lived single-use ticket keeps the long-lived JWT out of URLs, logs, and history. |
| Spec scope | **Frontend-facing only** | eval/debug deferred. |
| Money | integer `*_rub` (whole rubles) | Matches the dataset (`price_rub`, `budget_rub`, …). |
| IDs | opaque strings (UUID for new entities; seed groups keep `G-0001`-style ids) | — |
| Timestamps | RFC 3339 UTC | — |
| API version | OpenAPI **3.1**, base path `/api/v1` | JSON-Schema-aligned; can describe `text/event-stream`. |

## 4. Object model & lifecycle

```
User ──< Session (a "chat") ──< Run (one agent turn) ──< Message
                              └─> Plan (the route) ──> MapPoint[]  +  CalendarEvent[]
Group (reusable travel-party / trip context) ──< Member ──< Preference
A Run may be linked to a Group (the selected "context") and produces/updates a Plan.
```

**Run lifecycle**

1. `POST /chat` → `202 { run_id, session_id }` (a new session is created if `session_id` is omitted).
2. Client mints a stream ticket and opens `GET /chat/{run_id}/stream?ticket=...` (SSE).
3. The agent streams assistant text and emits a plan whose `plan_status` goes `building → ready | error`.
4. While `plan_status != ready`, the map is read-only (`editable=false`).
5. To revise: `POST /plans/{id}/modify` (batch of added/removed points + optional note) →
   `202 { run_id }`; the plan flips back to `building` and the agent rebuilds, streaming on the
   **new** run's stream.

**Answering a clarifying question** reuses `POST /chat` with
`{ in_reply_to_question_id, selected_option_ids?, freeform? }` — no separate endpoint.

## 5. Conventions

- **Auth scheme:** HTTP `Bearer` JWT (access token) on all endpoints except
  `register` / `login` / `refresh`.
- **Pagination:** `?limit=20&offset=0` → `{ items: [...], total, limit, offset }`.
- **Error envelope** (every non-2xx response):
  ```json
  { "error": { "code": "validation_error", "message": "human readable", "details": {} } }
  ```
  | code | HTTP | meaning |
  |---|---|---|
  | `validation_error` | 422 | malformed/invalid body or params |
  | `unauthorized` | 401 | missing/invalid credentials or token |
  | `token_expired` | 401 | access/refresh token expired |
  | `forbidden` | 403 | authenticated but not allowed |
  | `not_found` | 404 | unknown resource |
  | `conflict` | 409 | e.g. email already registered |
  | `plan_not_ready` | 409 | modify/accept attempted while `status != ready` |
  | `rate_limited` | 429 | too many requests |
  | `internal` | 500 | unexpected server error |

## 6. Endpoints

### 6.1 Auth

```
POST /auth/register   { name, email, password }
   201 → { user: {id,name,email,created_at},
           tokens: { access_token, refresh_token, token_type:"Bearer", expires_in } }   // auto-login
   409 conflict (email exists) · 422 validation

POST /auth/login      { email, password }
   200 → { access_token, refresh_token, token_type:"Bearer", expires_in, user:{...} }
   401 unauthorized

POST /auth/refresh    { refresh_token }
   200 → { access_token, token_type:"Bearer", expires_in, refresh_token }   // refresh rotated
   401 token_expired / unauthorized

POST /auth/logout     { refresh_token }   → 204    // revokes the refresh token

GET  /auth/me         → 200 { id, name, email, created_at }
```
Access token ~15 min, refresh ~30 d, claim `sub = user_id`.

### 6.2 Chat / Run

```
POST /chat
  {
    session_id?,                 // omit → starts a new chat (session)
    message?,                    // user text
    group_id?,                   // selected travel-group "context"
    in_reply_to_question_id?,    // when answering a clarifying question
    selected_option_ids?: [],    // closed-answer selection(s)
    freeform?                     // freeform answer when options don't fit
  }
  → 202 { run_id, session_id }
  Rule: provide message, OR (in_reply_to_question_id + selected_option_ids|freeform).
  404 (session/group) · 422

POST /chat/{run_id}/stream-ticket   (Bearer)
  → 200 { ticket, expires_in: 60 }   // short-lived, single-use, run-scoped

GET  /chat/{run_id}/stream?ticket=...
  → 200 text/event-stream (SSE)      // EventSource-friendly; reconnect via Last-Event-ID

POST /chat/{run_id}/cancel
  → 202 { run_id, status:"cancelling" }   · 409 if already finished
```

**SSE events** (`event:` name + JSON `data:`; every event carries an `id` for `Last-Event-ID`;
the stream closes on a terminal `run_status`):

```
run_status          { run_id, status: started|running|completed|cancelled|error }
message_delta       { run_id, message_id, delta }                       // streamed text chunk
message             { run_id, message: {id, role:"assistant", content, created_at} }
clarifying_question { run_id, question: {id, text,
                        options: [{id, label}], allow_freeform: bool} }
plan_status         { run_id, plan_id, status: building|ready|error, error? }
map                 { run_id, plan_id, points: [MapPoint] }             // full snapshot
error               { run_id, error: {code, message} }

MapPoint = { id, name, kind: origin|destination|stop, lat, lng, order, note? }
```

### 6.3 Sessions (= chats)

```
GET /sessions?limit&offset  → { items:[SessionSummary], total, limit, offset }
   SessionSummary = { id, summary, created_at, updated_at,
                      last_message_preview?, group_id?, latest_plan_id?, plan_status? }
                      //  summary = short summary of the first request

GET /sessions/{id}          → { id, summary, created_at, updated_at, group_id?,
                                messages:[Message], plans:[PlanSummary] }
   Message = { id, role:user|assistant, content, created_at, run_id?,
               question?: ClarifyingQuestion,                 // assistant message that asks
               answer?: {in_reply_to_question_id, selected_option_ids?, freeform?},  // user reply
               plan_ref?: {plan_id, status} }                 // assistant message that (re)built a plan
   ClarifyingQuestion = { id, text, options:[{id,label}], allow_freeform }
   PlanSummary = { plan_id, status, destination?, estimated_total_rub?, created_at }
```
The ordered `messages[]` is the full reconstructable timeline; on reload the frontend pulls the live
route via `/plans/{id}/map`.

### 6.4 Groups (reusable travel-party / trip context)

```
POST /groups
   { name, comment?, budget_rub?,
     origin_city?, destination?, start_date?, end_date?,   // optional — mirrors travel_groups.csv
     members: [ MemberInput ] }
   MemberInput = { full_name, age?, citizenship?, home_airport?, role_in_group?,
                   loyalty_program?, notes?,
                   preferences?: [ {type?, value?, comment?} ] }   // structured + free-text
   201 → Group

GET /groups?limit&offset     → { items:[GroupSummary], total, limit, offset }
   GroupSummary = { id, name, comment?, budget_rub?, destination?, member_count, created_at }
GET /groups/{id}             → Group   (members embedded)
GET /groups/{id}/members     → { items:[Member] }
GET /groups/{id}/preferences → { items:[ {member_id, full_name, preferences:[Preference]} ] }
GET /groups/{id}/plans       → { items:[PlanSummary] }

Group  = { id, name, comment?, budget_rub?, origin_city?, destination?,
           start_date?, end_date?, created_at, updated_at, members:[Member] }
Member = { id, full_name, age?, citizenship?, home_airport?, role_in_group?,
           loyalty_program?, notes?, preferences:[Preference] }
Preference = { id, type?, value?, comment? }
```
Trip fields (`origin_city`/`destination`/dates/`budget_rub`) are **optional**, so a group can be
either a pure reusable party or a fully-specified request — matching `travel_groups.csv` while
staying flexible. Member/preference fields mirror `travelers.csv` and `traveler_preferences.csv`.

### 6.5 Plans / Map / Calendar

```
GET  /plans/{id}            → Plan
   Plan = { id, session_id, group_id?, run_id,
            status: building|ready|error|accepted|rejected,
            summary?, destination?, start_date?, end_date?,
            decision_rationale?, estimated_total_rub?,
            items: { flight?: FlightSel, hotel?: HotelSel, tour?: TourSel },
            map_points:[MapPoint], created_at, updated_at }
   FlightSel = { flight_id, origin_city, destination, price_rub, baggage_included,
                 stops, departure_time, arrival_time, fare_type, notes? }
   HotelSel  = { hotel_id, destination, stars, price_per_night_rub, nights,
                 breakfast_included, free_cancellation, rating, notes? }
   TourSel   = { tour_id, destination, total_price_rub, includes_flight,
                 includes_transfer, hotel_id?, notes? }

POST /plans/{id}/accept     → 200 Plan(status:accepted)     · 409 plan_not_ready
POST /plans/{id}/reject     { reason? } → 200 Plan(status:rejected)
POST /plans/{id}/modify     { add:[{name, kind?, lat?, lng?, after_point_id?}],
                              remove:[point_id], note? }
                            → 202 { run_id }                · 409 plan_not_ready
   //  modify allowed only when status=ready; plan flips to building; agent rebuilds on the new run's stream

GET  /plans/{id}/map        → { plan_id, status, editable, points:[MapPoint], bounds? }
                            //  editable = (status == ready) — gates frontend editing
GET  /plans/{id}/calendar   → { plan_id, timezone?, events:[CalendarEvent] }
   CalendarEvent = { id, type: flight|hotel|tour|activity, title, start, end?,
                     location?, ref_id?, notes? }
```
`FlightSel`/`HotelSel`/`TourSel` mirror the CSV columns directly so the backend maps straight from
the SQLite rows. `reject` marks the plan rejected (terminal); the "correct and resubmit" path is
`modify`.

## 7. Data model mapping

| API schema | Source |
|---|---|
| `FlightSel` | `data/travelers/flights.csv` |
| `HotelSel` | `data/travelers/hotels.csv` (+ derived `nights`) |
| `TourSel` | `data/travelers/tours.csv` |
| `Group` (trip fields) | `data/travelers/travel_groups.csv` |
| `Member` | `data/travelers/travelers.csv` + `group_members.csv` (`role_in_group`) |
| `Preference` | `data/travelers/traveler_preferences.csv` |
| `Plan.decision_rationale`, `status` | `data/reference/*_recommendations.csv` |

## 8. Deliverable & file placement

Per `AGENTS.md` (each module owns a `SPECIFICATION.md` referenced from the root):

- `api/openapi.yaml` — the OpenAPI 3.1 ("Swagger") document with **all** endpoints above.
- `api/SPECIFICATION.md` — module spec describing the API surface and how it maps to the data.
- Root `SPECIFICATION.md` — global architecture, referencing `api/SPECIFICATION.md` and (later) the
  frontend module.
- This design doc lives at `docs/superpowers/specs/2026-06-13-travel-agent-api-design.md`.

## 9. Open items / future work

- `eval/*` and `debug/*` ops endpoints — separate spec.
- Plan versioning/history (revision list per plan) — out of scope for v1; current model keeps a
  single mutable plan per build chain.
