# Agent Module — Specification

**Status:** research baselines implemented; not yet the production Agent Service.

This module contains the current agent-side experiments: a progression of agent architectures,
policy-document vector RAG indexing, and QA prediction evaluation. It is intentionally separate from
the frozen [`agent-service/`](../agent-service/) contracts, which describe the future production
microservice boundary.

## Architecture progression (baselines)

Visual diagrams of every variant (B1 → B2 → B3 → Final) live in
[`architectures.html`](./architectures.html) (open in a browser; Mermaid), indexed from
[`ARCHITECTURES.md`](./ARCHITECTURES.md); problems/limitations in [`PROBLEMS.md`](./PROBLEMS.md). The
baselines share one evaluation harness (`data/qa/qa.jsonl` → `baselines/evaluate_predictions.py`) so
each step is comparable. **`Final` (`baselines/final_agent.py`) is the selected version** — best
balance at outcome 0.85 / entity 1.0:

- **B1 — single-agent Tool+RAG** (`baselines/llm_tool_rag_baseline.py`): one GigaChat ReAct agent
  with CSV tools + policy RAG, emits one JSON outcome. Baseline reasoning, no self-check.
- **B2 — LangGraph plan + validation tool** (`baselines/langgraph_plan_validate_baseline.py`):
  reuses B1's agent as the executor inside a `draft → validate → (replan | finalize)` graph. The
  `validate` node is a **deterministic validation tool — a local stub of the backend's Contract B
  `POST /internal/plans/validate`** (unknown ids, budget total vs. group budget, child +
  night-arrival); it is a guardrail/calculator, not the agent's reflection. The **LLM** decides what
  to do with the violations on replan (re-search / `clarification` / `rejection`), looping up to
  `MAX_DRAFTS=3`. Adds reasoning-by-replanning over B1; genuine agent self-reflection (an LLM critic
  node) is deferred to a later baseline.
- **B3 — MAS structured pipeline** (`baselines/mas_supervisor_baseline.py`): a fully-agentic
  multi-agent graph — `load_context` (deterministic offer pre-filter by destination) → `IntentAgent`
  (request type, effective budget extracted from the request, risk) → specialist analysts
  (flight / hotel / tour / policy, each returns structured JSON) → `Supervisor/Planner` (assembles the
  plan) → `FinalJsonAgent` (snaps to a strict `outcome_type` enum) → `CriticAgent` (LLM reflection,
  grounded by B2's `validate` as a consulted tool), looping to the supervisor up to `MAX_ROUNDS=2`.
  **Outcome decisions stay agentic — no deterministic decision gates:** escalation is allowed only
  when the PolicyAgent finds a concrete visa/document risk for an actual traveler (not a blanket flag),
  and the IntentAgent (not a regex) extracts the request-stated budget so an over-budget plan becomes
  clarification/rejection. **`entities` are decoupled from `outcome_type`** — the specialists' picks
  (`recommended_*`/`acceptable_ids`) are carried into the final answer regardless of outcome, so a
  correct id is reported even on escalation/clarification. Adds Action 3, Role 2, genuine Reflection. **Empirically B3 underperforms
  B2 on `outcome` while reaching higher `entity`** — a documented trade-off (MAS coordination cost +
  decisions made far from the data vs. B2's deterministic grounding); see
  [`ARCHITECTURES.md`](./ARCHITECTURES.md).
- **Final — synthesis (specialists + tool-grounded outcome)** (`baselines/final_agent.py`): combines
  B3's entity machinery (context + specialists, entity ≈ 1.0) with B2's outcome stability. The
  `feasibility` node is a **deterministic calculator — a tool, not a decision**: it computes
  `total_cost_rub` (no double-count of package tours), the effective budget (request-stated budget
  overrides the group budget), `within_budget`, structural violations (destination mismatch,
  child + night-arrival), **and the chosen plan's attributes** (`chosen`: flight direct/stops/baggage,
  hotel stars/breakfast/cancellation) so the agent can match them against the user's stated hard
  requirements — the requirement list is not hard-coded. The **agents still decide** — Supervisor and
  Critic (LLM) pick `outcome_type` from those reliable facts: `recommendation` only if `within_budget`
  **and** the chosen plan meets every stated hard requirement; otherwise **default `clarification`**,
  with `rejection` reserved for an explicit no-compromise request. Graph: `context → intent → specialists →
  feasibility → supervisor → finalizer → critic → (replan | end)`. This is B2's winning pattern —
  deterministic facts as a tool, agentic decision — plus B3's specialists, targeting high `outcome`
  **and** high `entity`. (An earlier fully-agentic FeasibilityAgent variant over-rejected because an
  LLM budget verdict is itself noisy; a calculator-tool restores B2's reliable grounding.)

## Scope

In scope:

- Build a Chroma index over `data/documents/*.md` using one markdown `##` section per chunk.
- Run a GigaChat LangChain agent with CSV tools and policy RAG (B1).
- Wrap that agent in a LangGraph plan/validate/replan loop with deterministic self-checks (B2).
- Evaluate predictions against `data/qa/qa.jsonl`.

Out of scope:

- Implementing Contract A (`agent-service/openapi.yaml`).
- Calling Contract B (`agent-service/internal-tools-openapi.yaml`) instead of local CSV files.
- Persisting LangGraph thread state.
- Serving HTTP or SSE.

## Files

| Path | Purpose |
|---|---|
| `requirements.txt` | Python dependencies for local agent experiments. |
| `scripts/build_policy_index.py` | Builds `data/indexes/policy_chroma/` from policy markdown files. |
| `baselines/llm_tool_rag_baseline.py` | **B1** — single-agent Tool+RAG baseline on one QA case or all cases. |
| `baselines/langgraph_plan_validate_baseline.py` | **B2** — LangGraph draft→validate→replan loop; reuses B1's agent + tools. |
| `baselines/mas_supervisor_baseline.py` | **B3** — MAS structured pipeline (intent + specialists + supervisor + critic). |
| `baselines/final_agent.py` | **Final** — B3 entity machinery + agentic FeasibilityAgent grounding the outcome; reuses B3 nodes. |
| `baselines/evaluate_predictions.py` | Scores baseline JSONL predictions against expected QA outcomes/entities. |

## Commands

```bash
pip install -r agent/requirements.txt
python agent/scripts/build_policy_index.py

# B1 — single-agent Tool+RAG
python agent/baselines/llm_tool_rag_baseline.py --all > baseline_predictions.jsonl
python agent/baselines/evaluate_predictions.py baseline_predictions.jsonl

# B2 — LangGraph plan + validate/replan (same harness, comparable metrics)
python agent/baselines/langgraph_plan_validate_baseline.py --all > b2_predictions.jsonl
python agent/baselines/evaluate_predictions.py b2_predictions.jsonl

# B3 — MAS supervisor + specialists + LLM critic
python agent/baselines/mas_supervisor_baseline.py --all > b3_predictions.jsonl
python agent/baselines/evaluate_predictions.py b3_predictions.jsonl

# Final — agentic synthesis (specialists + FeasibilityAgent-grounded outcome)
python agent/baselines/final_agent.py --all > final_predictions.jsonl
python agent/baselines/evaluate_predictions.py final_predictions.jsonl
```

Generated files are local artifacts and should not be committed:

- `baseline_predictions.jsonl`
- `data/indexes/`

## Relation to the final architecture

The baseline currently reads CSV files directly. The final Agent Service should instead keep the
same reasoning/RAG ideas but retrieve business data through the backend's internal tool API
(`agent-service/internal-tools-openapi.yaml`) and expose runs through
`agent-service/openapi.yaml`.
