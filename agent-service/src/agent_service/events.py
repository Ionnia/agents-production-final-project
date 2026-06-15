from __future__ import annotations

import uuid
from typing import Any

from .schemas import PlannerResult

# Coordinate lookup for dataset cities / airport codes (lat, lng), keyed by the airport code,
# the English name AND the Russian label the planner emits (group-less path → «Стамбул», group
# path via Contract B → "IST"). Unknown → None (skipped). Covers every dataset destination.
_COORDS: dict[str, tuple[float, float]] = {
    # Origins
    "MOSCOW": (55.7558, 37.6173),
    "МОСКВА": (55.7558, 37.6173),
    "SVO": (55.7558, 37.6173),
    "DME": (55.7558, 37.6173),
    "VKO": (55.7558, 37.6173),
    "ST PETERSBURG": (59.9311, 30.3609),
    "SAINT PETERSBURG": (59.9311, 30.3609),
    "SAINT-PETERSBURG": (59.9311, 30.3609),
    "САНКТ-ПЕТЕРБУРГ": (59.9311, 30.3609),
    "LED": (59.9311, 30.3609),
    # Destinations
    "IST": (41.0082, 28.9784),
    "ISTANBUL": (41.0082, 28.9784),
    "СТАМБУЛ": (41.0082, 28.9784),
    "AYT": (36.8841, 30.7056),
    "ANTALYA": (36.8841, 30.7056),
    "АНТАЛЬЯ": (36.8841, 30.7056),
    "DXB": (25.2048, 55.2708),
    "DUBAI": (25.2048, 55.2708),
    "ДУБАЙ": (25.2048, 55.2708),
    "BKK": (13.7563, 100.5018),
    "BANGKOK": (13.7563, 100.5018),
    "БАНГКОК": (13.7563, 100.5018),
    "BCN": (41.3874, 2.1686),
    "BARCELONA": (41.3874, 2.1686),
    "БАРСЕЛОНА": (41.3874, 2.1686),
    "HKT": (7.8804, 98.3923),
    "PHUKET": (7.8804, 98.3923),
    "ПХУКЕТ": (7.8804, 98.3923),
}


def _coords(name: str | None) -> tuple[float, float] | None:
    if not name:
        return None
    return _COORDS.get(name.strip().upper())


def _map_points(result: PlannerResult) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    order = 0
    origin = _coords(result.origin_city)
    if origin:
        points.append(
            {"name": result.origin_city, "kind": "origin", "lat": origin[0], "lng": origin[1], "order": order}
        )
        order += 1
    dest = _coords(result.destination)
    if dest and result.destination:
        points.append(
            {"name": result.destination, "kind": "destination", "lat": dest[0], "lng": dest[1], "order": order}
        )
    elif not points and result.destination:
        # Always provide at least one valid point (DraftPlan requires map_points).
        points.append({"name": result.destination, "kind": "destination", "lat": 0.0, "lng": 0.0, "order": 0})
    return points


def events_for(result: PlannerResult, agent_run_id: str) -> list[tuple[str, dict[str, Any]]]:
    """Translate a PlannerResult into the ordered Contract A SSE events the backend expects."""
    out: list[tuple[str, dict[str, Any]]] = []
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"

    def message_event() -> tuple[str, dict[str, Any]]:
        return (
            "message",
            {
                "agent_run_id": agent_run_id,
                "message": {"id": msg_id, "role": "assistant", "content": result.message},
            },
        )

    # A `message` event is only emitted for the `info` outcome. For every structured
    # outcome the backend already persists (and re-emits) the user-facing assistant
    # message — the plan-ready message for `recommendation`, the question text for
    # `clarification`, and the localized escalation/conflict text for
    # `escalation`/`rejection`. Emitting an extra `message` here made the backend
    # persist two assistant rows for the same turn, which surfaced as a duplicated
    # answer bubble in the chat (most visibly for clarifications, where the question
    # text and the message content are identical).

    if result.outcome_type == "recommendation":
        out.append(("plan_status", {"agent_run_id": agent_run_id, "status": "building"}))
        out.append(
            (
                "plan",
                {
                    "agent_run_id": agent_run_id,
                    "plan": {
                        "destination": result.destination,
                        "start_date": result.start_date,
                        "end_date": result.end_date,
                        "selections": {
                            "flight_id": result.flight_id,
                            "hotel_id": result.hotel_id,
                            "tour_id": result.tour_id,
                        },
                        "estimated_total_rub": result.estimated_total_rub,
                        "decision_rationale": result.decision_rationale,
                        "map_points": _map_points(result),
                    },
                },
            )
        )
        out.append(("plan_status", {"agent_run_id": agent_run_id, "status": "ready"}))
        out.append(("run_status", {"agent_run_id": agent_run_id, "status": "completed", "outcome": "recommendation"}))

    elif result.outcome_type == "clarification":
        question = {
            "id": f"q_{uuid.uuid4().hex[:12]}",
            "text": result.question_text or result.message,
            "options": [
                {"id": f"o{i}", "label": label} for i, label in enumerate(result.question_options)
            ],
            "allow_freeform": True,
        }
        out.append(("clarifying_question", {"agent_run_id": agent_run_id, "question": question}))
        out.append(("run_status", {"agent_run_id": agent_run_id, "status": "completed", "outcome": "clarification"}))

    elif result.outcome_type == "rejection":
        out.append(
            (
                "constraints_conflict",
                {
                    "agent_run_id": agent_run_id,
                    "message": result.message,
                    "suggested_relaxations": result.suggested_relaxations,
                },
            )
        )
        out.append(
            ("run_status", {"agent_run_id": agent_run_id, "status": "completed", "outcome": "constraints_conflict"})
        )

    elif result.outcome_type == "escalation":
        out.append(
            (
                "escalation",
                {
                    "agent_run_id": agent_run_id,
                    "reason": result.escalation_reason or "manual_review",
                    "message": result.message,
                },
            )
        )
        out.append(("run_status", {"agent_run_id": agent_run_id, "status": "completed", "outcome": "escalation"}))

    else:  # info
        out.append(message_event())
        out.append(("run_status", {"agent_run_id": agent_run_id, "status": "completed"}))

    return out
