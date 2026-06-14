from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Contract A request/response models (subset we need) ──────────────────────────────────────────

RunMode = Literal["new_trip", "modify", "answer", "qa"]


class Answer(BaseModel):
    in_reply_to_question_id: str
    selected_option_ids: list[str] | None = None
    freeform: str | None = None


class CreateRunRequest(BaseModel):
    external_run_id: str
    correlation_id: str
    session_id: str
    user_id: str
    mode: RunMode
    thread_id: str | None = None
    group_id: str | None = None
    active_plan_id: str | None = None
    message: str | None = None
    answer: Answer | None = None
    route_edits: dict[str, Any] | None = None
    locale: str | None = None
    metadata: dict[str, Any] | None = None


class RunCreated(BaseModel):
    agent_run_id: str
    thread_id: str
    status: Literal["started"] = "started"
    stream_url: str


class RunStatus(BaseModel):
    agent_run_id: str
    thread_id: str
    status: Literal["queued", "running", "completed", "cancelled", "error"]
    current_node: str | None = None
    outcome: str | None = None
    started_at: str
    finished_at: str | None = None
    error: dict[str, str] | None = None


class CancelResponse(BaseModel):
    agent_run_id: str
    status: Literal["cancelling"] = "cancelling"


class Health(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    detail: str | None = None


class ServiceInfo(BaseModel):
    service: str
    version: str
    model: str | None = None
    graph_version: str | None = None
    capabilities: list[str] = Field(default_factory=list)


# ── Planner result (internal, planner → SSE mapping) ─────────────────────────────────────────────

PlanOutcome = Literal["recommendation", "clarification", "rejection", "escalation", "info"]


class PlannerResult(BaseModel):
    """Normalized output of a planner; events.py maps it to Contract A SSE events."""

    outcome_type: PlanOutcome
    message: str
    flight_id: str | None = None
    hotel_id: str | None = None
    tour_id: str | None = None
    origin_city: str | None = None
    destination: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    estimated_total_rub: int | None = None
    decision_rationale: str | None = None
    # clarification
    question_text: str | None = None
    question_options: list[str] = Field(default_factory=list)
    # rejection (constraints_conflict)
    suggested_relaxations: list[str] = Field(default_factory=list)
    # escalation
    escalation_reason: str | None = None
