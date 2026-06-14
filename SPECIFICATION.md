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
┌──────────────┐  HTTP+SSE (/api/v1)  ┌──────────────────────┐
│  Frontend    │ ───────────────────▶ │  Backend API (BFF)   │ owns: users, sessions, plans,
│  (Vue 3+TS)  │ ◀─────────────────── │                      │ groups, business DB, access ctrl
└──────────────┘   plans·map·calendar └───┬──────────▲───────┘
                                          │          │
                       Contract A: /v1 runs+SSE   Contract B: /internal/*
                                          ▼          │ (business data + validate)
                                      ┌──────────────────────┐
                                      │  Agent Service        │ owns: LangGraph graph, threads,
                                      │  (LangGraph runtime)  │ prompts, LLM, RAG/Chroma
                                      └──────────────────────┘

Domain data (data/):  travelers·flights·hotels·tours → backend business DB;
                      documents → agent RAG;  reference·qa → eval.
```

- The **frontend** is a chat UI and talks only to the backend. The user converses with the agent,
  answers closed clarifying questions, watches the route render on a map, and edits it once ready.
- The **backend (BFF)** owns all business data and access control (users, sessions, plans, groups,
  the business DB). It authorizes the user, drives the agent, and proxies the agent's events to the
  frontend; it persists the plan the agent proposes.
- The **agent service** is a separate microservice (LangGraph runtime). It reasons, retrieves from
  policy documents (RAG), calls the LLM, and **pulls business data from the backend's internal API**
  (Variant B). It never talks to the frontend and never writes business data — it *proposes* a draft
  plan that the backend persists.
- **Contracts:** the only frontend↔backend surface is the `api/` module's OpenAPI document; the
  backend↔agent surface is the `agent-service/` module's two OpenAPI documents.
- The **domain data** (`data/`) is the synthetic dataset: offers/travelers back the business DB,
  policy documents back the agent's RAG, and reference/QA drive evaluation.

### Core interaction (async run model)

A chat message creates a **run** (one agent turn). The backend opens a run on the agent service
(`POST /v1/runs`) and forwards the agent's streamed events to the frontend's SSE: assistant text,
clarifying questions, map snapshots, and a `plan_status` of `building → ready | error`. While a plan
is not `ready` the map is read-only. The user corrects the route by submitting a batch of
added/removed points, which starts a new rebuild run. Lifecycles:
[`api/SPECIFICATION.md`](./api/SPECIFICATION.md) (frontend↔backend) and
[`agent-service/SPECIFICATION.md`](./agent-service/SPECIFICATION.md) (backend↔agent).

## 2. Modules

| Module | Path | Spec | Status |
|---|---|---|---|
| **Frontend↔Backend contract** | [`api/`](./api/) | [`api/SPECIFICATION.md`](./api/SPECIFICATION.md) → [`api/openapi.yaml`](./api/openapi.yaml) | Defined; not implemented |
| **Backend↔Agent contracts** | [`agent-service/`](./agent-service/) | [`agent-service/SPECIFICATION.md`](./agent-service/SPECIFICATION.md) → [`openapi.yaml`](./agent-service/openapi.yaml) + [`internal-tools-openapi.yaml`](./agent-service/internal-tools-openapi.yaml) | Defined; not implemented |
| **Frontend** | [`frontend/`](./frontend/) | [`frontend/SPECIFICATION.md`](./frontend/SPECIFICATION.md) | Implemented: chat UI, dithered backgrounds, side panel, plan map/calendar, auth — all mock-backed (MSW) |
| **Domain data** | [`data/`](./data/) | [`README.md`](./README.md) (dataset description) | Present (synthetic seed data) |
| **Backend service (BFF)** | _not in repo yet_ | — | Planned; implements the `api/` + `/internal` contracts, owns the business DB |
| **Agent Service** | _not in repo yet_ | — | Planned; implements Contract A; LangGraph + RAG/LLM |

### 2.1 Frontend↔Backend contract (`api/`)

The frontend-facing HTTP + SSE contract: auth (JWT), chat/run with SSE streaming, sessions (chat
history), groups (reusable travel-party context), and plans (route) with map and calendar. Money is
integer rubles; schemas mirror the `data/` columns so the backend maps straight from its rows.
Deferred to later specs: `eval/*` and `debug/*` ops endpoints, plan versioning. See
[`api/SPECIFICATION.md`](./api/SPECIFICATION.md).

### 2.2 Backend↔Agent contracts (`agent-service/`)

The inner boundary that lets the backend and agent teams develop independently — two frozen OpenAPI
3.1 documents: **Contract A** (`openapi.yaml`, Backend → Agent Service: create/stream/cancel runs
over `/v1`, SSE events) and **Contract B** (`internal-tools-openapi.yaml`, Agent → Backend Internal
Tool API over `/internal`: read business data + validate plans). The agent is a **stateful**
LangGraph runtime; it pulls business data via Contract B (Variant B) and **proposes** a draft plan
the backend persists. See [`agent-service/SPECIFICATION.md`](./agent-service/SPECIFICATION.md).

### 2.3 Frontend (`frontend/`)

Vue 3 + TypeScript + Vite + Tailwind v4 + Pinia + Vue Router 4 + MapLibre GL. The full application
is implemented and mock-backed via MSW 2: glassmorphism UI with dithered prerendered backgrounds (8
scenes, cursor color-lens), auth flow, chat with streamed SSE responses and clarifying questions, a
side panel with session/group/plan history, and a plan view with an interactive MapLibre map,
day-by-day itinerary calendar, offer cards, and inline plan editing. The API layer is typed end-to-end
from `api/openapi.yaml` via `openapi-typescript`. 17 unit/integration specs pass with Vitest. See
[`frontend/SPECIFICATION.md`](./frontend/SPECIFICATION.md) for the full module description.

### 2.4 Domain data (`data/`)

Synthetic seed data the agent reasons over, described in [`README.md`](./README.md):

- `travelers/` — travelers, travel groups, group membership, preferences, and the flight/hotel/tour
  offer tables (intended as `travelers.sqlite`).
- `reference/` — reference plans / graded recommendations (`*_recommendations.csv`).
- `qa/` — Q&A dataset for E2E evaluation.
- `documents/` — service policy documents for RAG (booking rules, fares & baggage, hotel policy,
  package tours).

## 3. Cross-cutting conventions

- **APIs:** OpenAPI 3.1. Frontend↔backend under `/api/v1` (Bearer **JWT**); backend↔agent under `/v1`
  and `/internal` (Bearer **service tokens** + `X-Correlation-ID`). SSE for run streaming; a shared
  error envelope throughout. Details in [`api/SPECIFICATION.md`](./api/SPECIFICATION.md) and
  [`agent-service/SPECIFICATION.md`](./agent-service/SPECIFICATION.md).
- **Money:** integer `*_rub` (whole rubles), matching the dataset.
- **IDs:** opaque strings — UUIDs for new entities; seeded groups keep `G-0001`-style ids.
- **Specs stay in sync with code** ([`AGENTS.md`](./AGENTS.md)): update the relevant module
  `SPECIFICATION.md` (and this root index) in the same change that touches the code.

## 4. Design history

- [`docs/superpowers/specs/2026-06-13-travel-agent-api-design.md`](./docs/superpowers/specs/2026-06-13-travel-agent-api-design.md)
  — approved design rationale behind the frontend↔backend API contract.
- [`docs/superpowers/specs/2026-06-14-backend-agent-api-design.md`](./docs/superpowers/specs/2026-06-14-backend-agent-api-design.md)
  — approved design rationale behind the backend↔agent contracts (stateful agent, Variant B).
