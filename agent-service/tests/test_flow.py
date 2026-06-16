"""Planner / run-manager behaviour for the multi-turn travel flow.

The heavyweight LLM graph is replaced by a fake runtime returning canned agent JSON, so
these exercise the agent-service glue the user's bug touched: conversation memory threaded
into the graph, clarifying-question options passed through, and group-less recommendations
forwarded (the backend re-validates at persist time).
"""
from __future__ import annotations

import json

import pytest

from agent_service.config import Settings
from agent_service.planner import Planner, user_text
from agent_service.runs import RunManager, ThreadState
from agent_service.schemas import Answer, CreateRunRequest, PlannerResult


class FakeRuntime:
    """Stands in for the Final LangGraph runtime; records the case it was handed."""

    def __init__(self, response: dict, memory: dict | None = None) -> None:
        self._response = response
        self._memory = memory or {"preferences": []}
        self.last_case: dict | None = None
        self.memory_calls: list[tuple[str, str, dict]] = []

    async def run(self, case: dict) -> str:
        self.last_case = case
        return json.dumps(self._response, ensure_ascii=False)

    async def extract_memory(self, latest_user_message: str, user_transcript: str, group_context: dict) -> dict:
        self.memory_calls.append((latest_user_message, user_transcript, group_context))
        return self._memory


class FakeContractB:
    def __init__(self, validation: dict | None = None) -> None:
        self._validation = validation or {"valid": True, "hard_violations": []}
        self.validated = False
        self.saved_preferences: list[dict] = []

    async def group_context(self, group_id: str, correlation_id: str) -> dict:
        return {
            "group_id": group_id,
            "origin_city": "Moscow",
            "destination": "IST",
            "members": [{"traveler_id": "T-1", "preferences": []}],
        }

    async def search_flights(self, body: dict, correlation_id: str) -> list[dict]:
        return []

    async def search_hotels(self, body: dict, correlation_id: str) -> list[dict]:
        return []

    async def search_tours(self, body: dict, correlation_id: str) -> list[dict]:
        return []

    async def validate_plan(self, body: dict, correlation_id: str) -> dict:
        self.validated = True
        return self._validation

    async def save_preferences(self, group_id: str, body: dict, correlation_id: str) -> dict:
        self.saved_preferences.extend(body.get("preferences", []))
        return {"saved": body.get("preferences", []), "skipped": []}


def _planner(
    response: dict,
    contract_b: FakeContractB | None = None,
    memory: dict | None = None,
) -> tuple[Planner, FakeRuntime]:
    planner = Planner(Settings(), contract_b or FakeContractB())
    runtime = FakeRuntime(response, memory)
    planner._final_runtime = runtime  # skip the heavyweight build
    return planner, runtime


def _run(mode: str = "new_trip", **kw) -> CreateRunRequest:
    base = dict(external_run_id="r1", correlation_id="c1", session_id="s1", user_id="u1", mode=mode)
    base.update(kw)
    return CreateRunRequest(**base)


@pytest.mark.asyncio
async def test_clarification_options_pass_through():
    planner, _ = _planner(
        {
            "outcome_type": "clarification",
            "entities": {},
            "answer": "К сожалению, по этому направлению нет предложений. Выберите доступное:",
            "options": ["Турция (Стамбул)", "ОАЭ (Дубай)", "Таиланд (Пхукет)"],
        }
    )
    result = await planner.plan(_run(message="Помоги спланировать путешествие по Греции"))
    assert result.outcome_type == "clarification"
    assert result.question_options == ["Турция (Стамбул)", "ОАЭ (Дубай)", "Таиланд (Пхукет)"]
    assert result.question_text  # falls back to the answer text


@pytest.mark.asyncio
async def test_group_less_recommendation_is_forwarded():
    planner, _ = _planner(
        {
            "outcome_type": "recommendation",
            "entities": {"flight_id": "FL-102", "hotel_id": "HT-045", "tour_id": None},
            "answer": "Подобрал поездку в Стамбул на 5–15 июля.",
            "options": [],
            "plan": {
                "origin_city": "Москва",
                "destination": "Стамбул",
                "start_date": "2026-07-05",
                "end_date": "2026-07-15",
                "estimated_total_rub": 148400,
            },
        }
    )
    # No group_id at all (the reported scenario) — must still recommend.
    result = await planner.plan(_run(message="Стамбул, вылет из Москвы, 5-15 июля, бюджет большой"))
    assert result.outcome_type == "recommendation"
    assert result.flight_id == "FL-102" and result.hotel_id == "HT-045"
    assert result.destination == "Стамбул" and result.origin_city == "Москва"
    assert result.start_date == "2026-07-05" and result.end_date == "2026-07-15"
    assert result.estimated_total_rub == 148400


@pytest.mark.asyncio
async def test_recommendation_without_selection_downgrades_to_clarification():
    planner, _ = _planner(
        {"outcome_type": "recommendation", "entities": {}, "answer": "Готово", "plan": {}}
    )
    result = await planner.plan(_run(message="Стамбул"))
    assert result.outcome_type == "clarification"


@pytest.mark.asyncio
async def test_group_recommendation_validated_via_contract_b_and_can_downgrade():
    contract_b = FakeContractB(
        {"valid": False, "hard_violations": [{"code": "budget_exceeded", "message": "Превышен бюджет"}]}
    )
    planner, _ = _planner(
        {
            "outcome_type": "recommendation",
            "entities": {"flight_id": "FL-102", "hotel_id": "HT-045", "tour_id": None},
            "answer": "План",
            "plan": {"destination": "Стамбул"},
        },
        contract_b,
    )
    result = await planner.plan(_run(message="Стамбул", group_id="G-0001"))
    assert contract_b.validated  # group path goes through Contract B
    assert result.outcome_type == "clarification"
    assert "Превышен бюджет" in result.question_options


@pytest.mark.asyncio
async def test_memory_agent_saves_high_confidence_group_preferences():
    contract_b = FakeContractB()
    planner, runtime = _planner(
        {"outcome_type": "clarification", "entities": {}, "answer": "ok", "options": []},
        contract_b,
        memory={
            "preferences": [
                {
                    "traveler_id": "T-1",
                    "type": "departure_time",
                    "value": "avoid_early_departure",
                    "comment": "Пользователь не любит ранние вылеты",
                    "confidence": 0.91,
                },
                {
                    "type": "destination",
                    "value": "istanbul",
                    "comment": "Разовый факт текущей поездки",
                    "confidence": 0.4,
                },
            ]
        },
    )
    await planner.plan(
        _run(
            message="Я обычно не люблю ранние вылеты, лучше после 10 утра",
            group_id="G-0001",
        )
    )
    assert runtime.memory_calls
    assert contract_b.saved_preferences == [
        {
            "traveler_id": "T-1",
            "type": "departure_time",
            "value": "avoid_early_departure",
            "comment": "Пользователь не любит ранние вылеты",
            "confidence": 0.91,
            "source": "agent_memory",
        }
    ]


@pytest.mark.asyncio
async def test_conversation_memory_is_threaded_into_the_graph():
    planner, runtime = _planner(
        {"outcome_type": "clarification", "entities": {}, "answer": "ok", "options": []}
    )
    thread = ThreadState(thread_id="thr_1")
    thread.messages = [
        {"role": "user", "content": "Помоги спланировать путешествие по Греции"},
        {"role": "assistant", "content": "Доступные направления: Турция (Стамбул), ОАЭ (Дубай)…"},
        {"role": "user", "content": "Город вылета Москва"},
    ]
    await planner.plan(_run(mode="answer", answer=Answer(in_reply_to_question_id="q1", freeform="Город вылета Москва")), thread)
    case = runtime.last_case
    # The full transcript reaches the graph (so it stops re-asking)…
    assert "Греции" in case["user_request"] and "Москва" in case["user_request"]
    assert "Ассистент:" in case["user_request"]
    # …while destination/origin matching sees only user text (never the agent's echoed options).
    assert "Ассистент" not in case["user_text_only"]
    assert "Москва" in case["user_text_only"]


@pytest.mark.asyncio
async def test_user_text_extracts_answer_modes():
    assert user_text(_run(message="привет")) == "привет"
    assert (
        user_text(_run(mode="answer", answer=Answer(in_reply_to_question_id="q", freeform="Москва")))
        == "Москва"
    )
    assert (
        user_text(
            _run(mode="answer", answer=Answer(in_reply_to_question_id="q", selected_option_labels=["Турция (Стамбул)"]))
        )
        == "Турция (Стамбул)"
    )


class RecordingPlanner:
    """Returns a scripted PlannerResult per call and records the threads it sees."""

    active_planner = "recording"

    def __init__(self, results: list[PlannerResult]) -> None:
        self._results = list(results)
        self.threads_seen: list[list[dict]] = []

    async def plan(self, req: CreateRunRequest, thread=None) -> PlannerResult:
        self.threads_seen.append(list(getattr(thread, "messages", []) or []))
        return self._results.pop(0)


async def _drain(mgr: RunManager, run) -> None:
    async for _ in mgr.stream(run, None):
        pass


@pytest.mark.asyncio
async def test_run_manager_accumulates_dialogue_across_turns():
    mgr = RunManager(Settings())
    mgr._planner = RecordingPlanner(
        [
            PlannerResult(outcome_type="clarification", message="Из какого города вылетаете?"),
            PlannerResult(outcome_type="clarification", message="Какие даты?"),
        ]
    )
    first = await mgr.start(_run(mode="new_trip", thread_id="thr_x", message="Путешествие по Греции"))
    await _drain(mgr, first)
    second = await mgr.start(
        _run(mode="answer", thread_id="thr_x", answer=Answer(in_reply_to_question_id="q1", freeform="Москва"))
    )
    await _drain(mgr, second)

    # The answer turn is recorded for EVERY mode, so by the 2nd run the thread carries the
    # whole dialogue — the bug was that clarifying answers were dropped from memory.
    messages = mgr.threads["thr_x"].messages
    contents = [m["content"] for m in messages]
    assert "Путешествие по Греции" in contents
    assert "Из какого города вылетаете?" in contents  # prior assistant question remembered
    assert "Москва" in contents  # the user's answer is in memory
    # The 2nd planner call already saw the accumulated history.
    assert any("Москва" in m["content"] for m in mgr._planner.threads_seen[1])
