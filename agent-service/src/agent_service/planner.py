from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from .config import Settings
from .contract_b import ContractBClient, ContractBError
from .schemas import CreateRunRequest, PlannerResult


class Planner:
    """Adapter from Contract A runs to the experimental Final agent graph."""

    def __init__(self, settings: Settings, contract_b: ContractBClient) -> None:
        self._settings = settings
        self._b = contract_b
        self._final_runtime: _FinalAgentRuntime | None = None
        self._runtime_lock = asyncio.Lock()
        self.active_planner = "final_agent"

    async def plan(self, run: CreateRunRequest) -> PlannerResult:
        if self._final_runtime is None:
            # Serialize the heavyweight, side-effectful runtime construction so concurrent runs
            # cannot both build it (sys.path / os.environ / module globals are process-shared).
            async with self._runtime_lock:
                if self._final_runtime is None:
                    self._final_runtime = _FinalAgentRuntime(self._settings)
        user_text = self._user_text(run)
        if not user_text:
            return PlannerResult(
                outcome_type="clarification",
                message="Уточните, пожалуйста, что нужно подобрать или изменить.",
                question_text="Что нужно подобрать или изменить?",
            )

        raw = await self._final_runtime.run(
            {
                "case_id": run.external_run_id or run.correlation_id,
                "category": _category_for_mode(run.mode),
                "group_id": run.group_id,
                "user_request": user_text,
            }
        )
        draft = _parse_agent_json(raw)
        if not draft:
            return PlannerResult(
                outcome_type="clarification",
                message="Не удалось надежно разобрать ответ агента. Уточните запрос или повторите попытку.",
                question_text="Повторить подбор с теми же условиями?",
                question_options=["Да, повторить", "Я уточню условия"],
            )

        context = await self._group_context(run)
        entities = draft.get("entities") if isinstance(draft.get("entities"), dict) else {}
        result = PlannerResult(
            outcome_type=_coerce_outcome(draft.get("outcome_type")),
            message=str(draft.get("answer") or ""),
            flight_id=entities.get("flight_id"),
            hotel_id=entities.get("hotel_id"),
            tour_id=entities.get("tour_id"),
            origin_city=context.get("origin_city"),
            destination=context.get("destination"),
            start_date=context.get("start_date"),
            end_date=context.get("end_date"),
            decision_rationale=str(draft.get("answer") or ""),
        )

        if result.outcome_type == "recommendation":
            # A recommendation may only be emitted once the backend has validated the draft
            # (SPECIFICATION.md §3). Validation requires a group_id (Contract B
            # POST /internal/plans/validate body), and on any failure/unavailability we must
            # NOT fail open — we downgrade to clarification instead of recommending unvalidated.
            if run.group_id:
                validation = await self._validate_ids(
                    run, result.flight_id, result.hotel_id, result.tour_id
                )
            else:
                validation = {
                    "valid": False,
                    "hard_violations": [
                        {
                            "code": "validation_unavailable",
                            "message": "невозможно проверить план без group_id",
                        }
                    ],
                }
            if not bool(validation.get("valid", True)):
                reasons = [
                    item.get("message", item.get("code", "нарушение ограничения"))
                    for item in validation.get("hard_violations", [])
                ] or ["backend validation rejected the draft plan"]
                return PlannerResult(
                    outcome_type="clarification",
                    message="Нужно уточнить условия: " + "; ".join(reasons),
                    question_text="Какое условие можно смягчить?",
                    question_options=reasons,
                    flight_id=result.flight_id,
                    hotel_id=result.hotel_id,
                    tour_id=result.tour_id,
                    origin_city=result.origin_city,
                    destination=result.destination,
                    start_date=result.start_date,
                    end_date=result.end_date,
                    decision_rationale=result.decision_rationale,
                )

        if result.outcome_type == "clarification" and not result.question_text:
            result.question_text = result.message
        if result.outcome_type == "rejection" and not result.suggested_relaxations:
            result.suggested_relaxations = [result.message]
        if result.outcome_type == "escalation" and not result.escalation_reason:
            result.escalation_reason = result.message
        return result

    async def _group_context(self, run: CreateRunRequest) -> dict[str, Any]:
        if not run.group_id:
            return {}
        try:
            return await self._b.group_context(run.group_id, run.correlation_id)
        except ContractBError:
            return {}

    async def _validate_ids(
        self, run: CreateRunRequest, flight_id: str | None, hotel_id: str | None, tour_id: str | None
    ) -> dict[str, Any]:
        try:
            return await self._b.validate_plan(
                {
                    "group_id": run.group_id,
                    "plan": {
                        "flight_id": flight_id,
                        "hotel_id": hotel_id,
                        "tour_id": tour_id,
                        "total_cost_rub": None,
                    },
                },
                run.correlation_id,
            )
        except ContractBError:
            # Do NOT fail open: an unreachable/erroring validation backend must downgrade the
            # recommendation to clarification, never emit an unvalidated plan (SPECIFICATION.md §3).
            return {
                "valid": False,
                "hard_violations": [
                    {
                        "code": "validation_unavailable",
                        "message": "сервис проверки плана недоступен",
                    }
                ],
            }

    def _user_text(self, run: CreateRunRequest) -> str:
        if run.mode in {"new_trip", "qa"} and run.message:
            return run.message
        if run.mode == "answer" and run.answer:
            return run.answer.freeform or " ".join(
                run.answer.selected_option_labels or run.answer.selected_option_ids or []
            )
        if run.mode == "modify" and run.route_edits:
            return run.route_edits.get("note") or "пересобери маршрут"
        return ""


def _category_for_mode(mode: str) -> str:
    return {
        "new_trip": "planning",
        "modify": "replanning",
        "answer": "clarification",
        "qa": "info",
    }.get(mode, "planning")


def _coerce_outcome(value: Any) -> str:
    if value in {"recommendation", "clarification", "rejection", "escalation", "info"}:
        return value
    return "clarification"


def _parse_agent_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def _build_llm(settings: Settings):
    from langchain_gigachat import GigaChat

    if not settings.gigachat_credentials:
        raise RuntimeError("GIGACHAT_CREDENTIALS is required for agent-service.")
    return GigaChat(
        credentials=settings.gigachat_credentials,
        scope=settings.gigachat_scope,
        model=settings.gigachat_model,
        verify_ssl_certs=False,
        temperature=0,
    )


class _FinalAgentRuntime:
    def __init__(self, settings: Settings) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        baselines = repo_root / "agent" / "baselines"
        if str(baselines) not in sys.path:
            sys.path.insert(0, str(baselines))

        os.environ["GIGACHAT_CREDENTIALS"] = settings.gigachat_credentials
        os.environ["GIGACHAT_SCOPE"] = settings.gigachat_scope
        os.environ["GIGACHAT_MODEL"] = settings.gigachat_model

        import final_agent
        import mas_supervisor_baseline as b3

        final_agent.b1.build_agent()
        b3.LLM = _build_llm(settings)
        self._final_agent = final_agent
        self._app = final_agent.build_graph()
        self._lock = asyncio.Lock()

    async def run(self, case: dict[str, Any]) -> str:
        async with self._lock:
            return await asyncio.to_thread(self._final_agent.run_case, self._app, case)
