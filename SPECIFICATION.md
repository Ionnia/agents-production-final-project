# Travel-Planning Agent — Global Specification

Final project of the course **«Промышленная разработка агентов»** (Industrial development of
agents): a travel-planning agent that selects optimal flights, hotels, and tours for a travel group
given its composition, budget, constraints, and preferences, and rebuilds the plan when the user
changes the inputs.

This root document describes the **global architecture** and indexes each module's own
`SPECIFICATION.md`. Per [`AGENTS.md`](./AGENTS.md), every change must keep this file and the relevant
module spec in sync with the code.

## 1. System overview

```
┌────────────────┐    HTTP + SSE (/api/v1)    ┌────────────────────┐
│  Frontend      │ ─────────────────────────▶ │  Agent backend     │
│  (Vue 3 + TS)  │ ◀───────────────────────── │  (LLM + tools)     │
│  chat + map +  │      runs / plans / map     │                    │
│  calendar UI   │                             └─────────┬──────────┘
└────────────────┘                                       │ tools (DB / RAG)
                                                          ▼
                                              ┌────────────────────────┐
                                              │  Domain data (data/)    │
                                              │  travelers · flights ·  │
                                              │  hotels · tours ·       │
                                              │  documents · reference  │
                                              └────────────────────────┘
```

- The **frontend** is a chat UI. The user converses with the agent, answers closed clarifying
  questions, watches the route render on a map, and edits it once it is ready.
- The **backend** runs the agent: it interprets the request, queries the domain data through tools,
  answers from policy documents (RAG), and produces a **plan** (selected flight/hotel/tour + route +
  calendar). It streams progress back over SSE.
- The **contract** between them — the only integration surface the frontend depends on — is the
  `api/` module's OpenAPI document.
- The **domain data** (`data/`) is the synthetic dataset the agent reasons over.

### Core interaction (async run model)

A chat message creates a **run** (one agent turn); the run streams typed events (assistant text,
clarifying questions, map snapshots, and a `plan_status` of `building → ready | error`). While a plan
is not `ready` the map is read-only. The user corrects the route by submitting a batch of
added/removed points, which starts a new rebuild run. Full lifecycle: [`api/SPECIFICATION.md`](./api/SPECIFICATION.md).

## 2. Modules

| Module | Path | Spec | Status |
|---|---|---|---|
| **API contract** | [`api/`](./api/) | [`api/SPECIFICATION.md`](./api/SPECIFICATION.md) → [`api/openapi.yaml`](./api/openapi.yaml) | Defined; not implemented |
| **Frontend** | [`frontend/`](./frontend/) | [`frontend/src/SPEC.md`](./frontend/src/SPEC.md) (UI/visual scenes) | UI shell + animated backgrounds; API client not built |
| **Domain data** | [`data/`](./data/) | [`README.md`](./README.md) (dataset description) | Present (synthetic seed data) |
| **Agent backend** | _not in repo yet_ | — | Planned; owns the agent, tools, and SQLite schema |

### 2.1 API contract (`api/`)

The frontend-facing HTTP + SSE contract: auth (JWT), chat/run with SSE streaming, sessions (chat
history), groups (reusable travel-party context), and plans (route) with map and calendar. Money is
integer rubles; schemas mirror the `data/` columns so the backend maps straight from its rows.
Deferred to later specs: `eval/*` and `debug/*` ops endpoints, plan versioning. See
[`api/SPECIFICATION.md`](./api/SPECIFICATION.md).

### 2.2 Frontend (`frontend/`)

Vue 3 + TypeScript + Vite. Today it provides the visual shell — a styled chat input
(`src/components/AgentChat/`) and animated "torn magazine scrapbook" page backgrounds
(`src/components/PageBackground/`, specified in [`frontend/src/SPEC.md`](./frontend/src/SPEC.md)). It
does not yet contain an API client; it will consume the `api/` contract (a dedicated
frontend-behavior spec is future work).

### 2.3 Domain data (`data/`)

Synthetic seed data the agent reasons over, described in [`README.md`](./README.md):

- `travelers/` — travelers, travel groups, group membership, preferences, and the flight/hotel/tour
  offer tables (intended as `travelers.sqlite`).
- `reference/` — reference plans / graded recommendations (`*_recommendations.csv`).
- `qa/` — Q&A dataset for E2E evaluation.
- `documents/` — service policy documents for RAG (booking rules, fares & baggage, hotel policy,
  package tours).

## 3. Cross-cutting conventions

- **API:** OpenAPI 3.1 under base path `/api/v1`; Bearer JWT auth; SSE for run streaming; standard
  error envelope and pagination. Details in [`api/SPECIFICATION.md`](./api/SPECIFICATION.md).
- **Money:** integer `*_rub` (whole rubles), matching the dataset.
- **IDs:** opaque strings — UUIDs for new entities; seeded groups keep `G-0001`-style ids.
- **Specs stay in sync with code** ([`AGENTS.md`](./AGENTS.md)): update the relevant module
  `SPECIFICATION.md` (and this root index) in the same change that touches the code.

## 4. Design history

- [`docs/superpowers/specs/2026-06-13-travel-agent-api-design.md`](./docs/superpowers/specs/2026-06-13-travel-agent-api-design.md)
  — approved design rationale behind the API contract.
