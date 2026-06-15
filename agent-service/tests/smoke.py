"""Standalone smoke test (no pytest needed): run with the project venv.

    .venv/bin/python agent-service/tests/smoke.py

Covers the Contract A HTTP surface (TestClient) and the run/SSE pipeline with a fake planner.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent-service" / "src"))
os.environ.setdefault("AGENT_SERVICE_TOKEN", "test-token")

from fastapi.testclient import TestClient  # noqa: E402

from agent_service.config import Settings  # noqa: E402
from agent_service.events import events_for  # noqa: E402
from agent_service.main import app  # noqa: E402
from agent_service.runs import RunManager  # noqa: E402
from agent_service.planner import Planner  # noqa: E402
from agent_service.schemas import Answer, CreateRunRequest, PlannerResult  # noqa: E402

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}", "X-Correlation-ID": "corr-1"}
ok = 0
fail = 0


def check(name: str, cond: bool) -> None:
    global ok, fail
    print(("PASS" if cond else "FAIL"), name)
    ok += cond
    fail += not cond


# ── 1. HTTP contract ─────────────────────────────────────────────────────────────────────────
with TestClient(app) as client:
    check("health no-auth 200 ok", client.get("/v1/health").json().get("status") == "ok")
    check("info requires token (401)", client.get("/v1/info").status_code == 401)
    check("info with token 200", client.get("/v1/info", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200)
    check("create run requires token (401)", client.post("/v1/runs", json={}).status_code == 401)

    body = {
        "external_run_id": "run-1", "correlation_id": "corr-1", "session_id": "s1",
        "user_id": "u1", "mode": "qa", "message": "Можно ли бесплатно отменить отель?",
    }
    resp = client.post("/v1/runs", json=body, headers=AUTH)
    created = resp.json()
    check("create run 202", resp.status_code == 202)
    check("create run status=started", created.get("status") == "started")
    check(
        "stream_url path correct",
        created.get("stream_url") == f"/v1/runs/{created.get('agent_run_id')}/stream",
    )
    check("get unknown run 404", client.get("/v1/runs/nope", headers=AUTH).status_code == 404)


# ── 2. events_for mapping ─────────────────────────────────────────────────────────────────────
rec = PlannerResult(outcome_type="recommendation", message="ok", flight_id="FL-102",
                    hotel_id="HT-045", destination="IST", origin_city="Moscow", estimated_total_rub=130500)
names = [n for n, _ in events_for(rec, "ar1")]
# No redundant `message` event: the backend persists/relays the plan-ready message itself,
# so emitting one here duplicated the assistant bubble.
check("recommendation event order", names == ["plan_status", "plan", "plan_status", "run_status"])
plan_data = events_for(rec, "ar1")[1][1]["plan"]
check("plan has selections", plan_data["selections"]["flight_id"] == "FL-102")
check("plan has map_points", len(plan_data["map_points"]) >= 1)

clar = PlannerResult(outcome_type="clarification", message="?", question_text="q", question_options=["a"])
clar_names = [n for n, _ in events_for(clar, "ar1")]
check("clarification emits question", clar_names[0] == "clarifying_question")
# The question carries the user-facing text; no separate `message` event (it duplicated it).
check("clarification has no duplicate message event", "message" not in clar_names)
rej = PlannerResult(outcome_type="rejection", message="no", suggested_relaxations=["x"])
check("rejection -> constraints_conflict + outcome", events_for(rej, "ar1")[-1][1]["outcome"] == "constraints_conflict")
info = PlannerResult(outcome_type="info", message="just info")
check("info still emits its message", [n for n, _ in events_for(info, "ar1")] == ["message", "run_status"])

answer_text = Planner._user_text(
    object.__new__(Planner),
    CreateRunRequest(
        external_run_id="answer-1",
        correlation_id="corr-answer",
        session_id="s1",
        user_id="u1",
        mode="answer",
        answer=Answer(
            in_reply_to_question_id="q-budget",
            selected_option_ids=["o0"],
            selected_option_labels=["Увеличить бюджет"],
        ),
    ),
)
check("answer text uses selected labels", answer_text == "Увеличить бюджет")


# ── 3. run/SSE pipeline with fake planner ─────────────────────────────────────────────────────
class FakePlanner:
    active_planner = "fake"
    async def plan(self, req: CreateRunRequest, thread=None) -> PlannerResult:
        return rec


async def run_pipeline() -> list[str]:
    mgr = RunManager(Settings())
    mgr._planner = FakePlanner()
    req = CreateRunRequest(external_run_id="r", correlation_id="c", session_id="s",
                           user_id="u", mode="new_trip", group_id="G-0001", message="поездка")
    run = await mgr.start(req)
    seen = []
    async for event in mgr.stream(run, None):
        seen.append(event.event)
    return seen, run


seen, run = asyncio.run(run_pipeline())
check("pipeline streams running..completed", seen[0] == "run_status" and seen[-1] == "run_status")
check("pipeline reached completed", run.status == "completed" and run.outcome == "recommendation")
check("pipeline emitted plan", "plan" in seen)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
