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

    async def plan(self, run: CreateRunRequest, thread: Any | None = None) -> PlannerResult:
        if self._final_runtime is None:
            # Serialize the heavyweight, side-effectful runtime construction so concurrent runs
            # cannot both build it (sys.path / os.environ / module globals are process-shared).
            async with self._runtime_lock:
                if self._final_runtime is None:
                    self._final_runtime = _FinalAgentRuntime(self._settings)
        latest = user_text(run)
        if not latest:
            return PlannerResult(
                outcome_type="clarification",
                message="Уточните, пожалуйста, что нужно подобрать или изменить.",
                question_text="Что нужно подобрать или изменить?",
            )

        # Conversation memory: the agent graph is single-shot, so we feed it the whole
        # transcript (so it never re-asks for something already said) plus the user-only text
        # (so deterministic destination/origin matching never trips over the agent's own
        # option labels echoed back in its prior questions).
        transcript, user_only = _conversation(thread, latest)
        await self._remember_preferences(run, latest, user_only)
        backend_context = await self._backend_context(run, user_only)
        raw = await self._final_runtime.run(
            {
                "case_id": run.external_run_id or run.correlation_id,
                "category": _category_for_mode(run.mode),
                "group_id": run.group_id,
                "user_request": transcript,
                "user_text_only": user_only,
                **({"backend_context": backend_context} if backend_context else {}),
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
        plan_block = draft.get("plan") if isinstance(draft.get("plan"), dict) else {}
        options = [str(o).strip() for o in (draft.get("options") or []) if str(o).strip()]
        result = PlannerResult(
            outcome_type=_coerce_outcome(draft.get("outcome_type")),
            message=str(draft.get("answer") or ""),
            flight_id=entities.get("flight_id"),
            hotel_id=entities.get("hotel_id"),
            tour_id=entities.get("tour_id"),
            origin_city=plan_block.get("origin_city") or context.get("origin_city"),
            destination=plan_block.get("destination") or context.get("destination"),
            start_date=plan_block.get("start_date") or context.get("start_date"),
            end_date=plan_block.get("end_date") or context.get("end_date"),
            estimated_total_rub=_as_int(plan_block.get("estimated_total_rub")),
            decision_rationale=str(draft.get("answer") or ""),
            question_options=options,
        )

        if result.outcome_type == "recommendation":
            if not (result.flight_id or result.hotel_id or result.tour_id):
                # A recommendation with no concrete selection is not actionable — clarify.
                return PlannerResult(
                    outcome_type="clarification",
                    message=result.message or "Уточните, пожалуйста, детали поездки.",
                    question_text=result.message or "Уточните, пожалуйста, детали поездки.",
                    question_options=options,
                )
            # SPECIFICATION.md §3: a recommendation must be validated before it is emitted.
            # When a group_id is present we validate via Contract B and never fail open. Without
            # a group_id the backend re-validates the draft at persist time (it ignores
            # `plan_status: ready` until the draft passes validate_selection and is stored), so
            # the backend remains the authority — we forward the agent's grounded recommendation.
            if run.group_id:
                validation = await self._validate_ids(
                    run, result.flight_id, result.hotel_id, result.tour_id
                )
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

    async def _remember_preferences(self, run: CreateRunRequest, latest: str, user_only: str) -> None:
        if not run.group_id or self._final_runtime is None:
            return
        extractor = getattr(self._final_runtime, "extract_memory", None)
        if extractor is None:
            return
        try:
            group = await self._group_context(run)
            updates = await extractor(latest, user_only, group)
            preferences = _normalize_memory_updates(updates)
            if preferences:
                await self._b.save_preferences(
                    run.group_id,
                    {"preferences": preferences},
                    run.correlation_id,
                )
        except Exception:
            return

    async def _backend_context(self, run: CreateRunRequest, user_only: str) -> dict[str, Any]:
        group: dict[str, Any] | None = None
        origin: str | None = None
        destination: str | None = None

        if run.group_id:
            group = await self._group_context(run)
            origin = _text_or_none(group.get("origin_city"))
            destination = _text_or_none(group.get("destination"))
        else:
            try:
                import travel_catalog as cat

                available = list(cat.DESTINATION_CATALOG.keys())
                destinations = cat.match_destinations(user_only, available)
                destination = destinations[0] if len(destinations) == 1 else None
                origin = cat.match_origin(user_only)
            except Exception:
                return {}

        if not origin or not destination:
            return {"group": _legacy_group(group)} if group else {}

        flights_task = self._safe_search(
            self._b.search_flights,
            {"origin": origin, "destination": destination},
            run.correlation_id,
        )
        hotels_task = self._safe_search(
            self._b.search_hotels,
            {"destination": destination},
            run.correlation_id,
        )
        tours_task = self._safe_search(
            self._b.search_tours,
            {"destination": destination},
            run.correlation_id,
        )
        flights, hotels, tours = await asyncio.gather(flights_task, hotels_task, tours_task)
        return {
            "source": "backend_contract_b",
            "group": _legacy_group(group),
            "members": _legacy_members(group),
            "preferences": _legacy_preferences(group),
            "resolved": {
                "origin_code": origin,
                "destination_code": destination,
                "start_date": group.get("start_date") if group else None,
                "end_date": group.get("end_date") if group else None,
                "budget_rub": group.get("budget_rub") if group else None,
            },
            "flights": [_legacy_offer(row) for row in flights],
            "hotels": [_legacy_offer(row) for row in hotels],
            "tours": [_legacy_offer(row) for row in tours],
        }

    async def _safe_search(self, func: Any, body: dict[str, Any], correlation_id: str) -> list[dict[str, Any]]:
        try:
            return await func(body, correlation_id)
        except ContractBError:
            return []

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
        # Kept for back-compat (callers/tests that reach for Planner._user_text); the logic
        # lives in the module-level ``user_text`` so runs.py can reuse it without a Planner.
        return user_text(run)


def user_text(run: CreateRunRequest) -> str:
    """The plain user text of a run, regardless of mode (message / answer / modify note)."""
    if run.mode in {"new_trip", "qa"} and run.message:
        return run.message
    if run.mode == "answer" and run.answer:
        return run.answer.freeform or " ".join(
            run.answer.selected_option_labels or run.answer.selected_option_ids or []
        )
    if run.mode == "modify" and run.route_edits:
        return run.route_edits.get("note") or "пересобери маршрут"
    return ""


def _conversation(thread: Any | None, latest: str) -> tuple[str, str]:
    """Build (full transcript, user-only text) from a thread's accumulated messages.

    ``thread.messages`` already includes the current user turn (runs.py appends it before
    planning), so the transcript is the complete dialogue. When there is no thread we fall
    back to the single latest turn (e.g. QA / first message)."""
    messages = getattr(thread, "messages", None) or []
    if not messages:
        return latest, latest
    lines: list[str] = []
    user_only: list[str] = []
    for message in messages:
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if message.get("role") == "user":
            lines.append(f"Пользователь: {content}")
            user_only.append(content)
        else:
            lines.append(f"Ассистент: {content}")
    transcript = "\n".join(lines) or latest
    return transcript, ("\n".join(user_only) or latest)


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _legacy_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return "1" if value else "0"
    return str(value)


def _legacy_offer(row: dict[str, Any]) -> dict[str, str]:
    return {
        key: _legacy_bool(value) if isinstance(value, bool) else str(value)
        for key, value in row.items()
        if value is not None
    }


def _legacy_group(group: dict[str, Any] | None) -> dict[str, str] | None:
    if not group:
        return None
    mapping = {
        "group_id": group.get("group_id") or group.get("id"),
        "origin_city": group.get("origin_city"),
        "destination": group.get("destination"),
        "start_date": group.get("start_date"),
        "end_date": group.get("end_date"),
        "budget_rub": group.get("budget_rub"),
    }
    return {key: str(value) for key, value in mapping.items() if value is not None}


def _legacy_members(group: dict[str, Any] | None) -> list[dict[str, str]]:
    if not group:
        return []
    members = group.get("members") or []
    return [
        {key: str(value) for key, value in member.items() if key != "preferences" and value is not None}
        for member in members
        if isinstance(member, dict)
    ]


def _legacy_preferences(group: dict[str, Any] | None) -> list[dict[str, str]]:
    if not group:
        return []
    out: list[dict[str, str]] = []
    for member in group.get("members") or []:
        if not isinstance(member, dict):
            continue
        traveler_id = member.get("traveler_id") or member.get("id")
        for pref in member.get("preferences") or []:
            if not isinstance(pref, dict):
                continue
            row = {key: str(value) for key, value in pref.items() if value is not None}
            if traveler_id:
                row["traveler_id"] = str(traveler_id)
            out.append(row)
    return out


def _normalize_memory_updates(updates: Any) -> list[dict[str, Any]]:
    if not isinstance(updates, dict):
        return []
    raw_items = updates.get("preferences")
    if not isinstance(raw_items, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        confidence = item.get("confidence")
        try:
            confidence_value = float(confidence) if confidence is not None else 1.0
        except (TypeError, ValueError):
            confidence_value = 0.0
        if confidence_value < 0.75:
            continue
        pref_type = _clean_memory_text(item.get("type"), 100)
        pref_value = _clean_memory_text(item.get("value"), 300)
        comment = _clean_memory_text(item.get("comment"), 500)
        if not (pref_type or pref_value or comment):
            continue
        key = (pref_type, pref_value, comment)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                **({"traveler_id": _clean_memory_text(item.get("traveler_id"), 120)} if item.get("traveler_id") else {}),
                "type": pref_type,
                "value": pref_value,
                "comment": comment,
                "confidence": round(confidence_value, 3),
                "source": "agent_memory",
            }
        )
    return normalized[:10]


def _clean_memory_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


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

        import final_agent_ranked as final_agent
        import mas_supervisor_baseline as b3

        final_agent.b1.build_agent()
        b3.LLM = _build_llm(settings)
        self._b3 = b3
        self._final_agent = final_agent
        self._app = final_agent.build_graph()
        self._lock = asyncio.Lock()

    async def run(self, case: dict[str, Any]) -> str:
        async with self._lock:
            return await asyncio.to_thread(self._final_agent.run_case, self._app, case)

    async def extract_memory(
        self,
        latest_user_message: str,
        user_transcript: str,
        group_context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = (
            "Ты MemoryAgent travel-сервиса. Извлеки из последней реплики пользователя только "
            "устойчивые предпочтения/ограничения, которые стоит сохранить во внешнюю память группы "
            "для будущих шагов. Не сохраняй разовые факты текущей поездки: конкретное направление, "
            "город вылета, даты, ответы на уточнение и одноразовый бюджет, если пользователь не говорит "
            "'обычно/всегда/предпочитаю/не люблю'.\n"
            "Разрешённые type: baggage, departure_time, arrival_time, flight, hotel_stars, meal, "
            "cancellation, budget_style, trip_style, traveler_composition, documents, accessibility, other.\n"
            "value пиши коротким стабильным кодом на английском/snake_case, comment — краткое русское "
            "объяснение. confidence ставь 0..1. Если сохранять нечего — preferences=[].\n"
            "Верни только minified JSON: "
            "{\"preferences\":[{\"traveler_id\":null,\"type\":\"...\",\"value\":\"...\","
            "\"comment\":\"...\",\"confidence\":0.0}]}\n"
            f"Контекст группы: {json.dumps(group_context, ensure_ascii=False)[:3000]}\n"
            f"Вся пользовательская часть диалога: {user_transcript[:3000]}\n"
            f"Последняя реплика: {latest_user_message}"
        )
        data = await asyncio.to_thread(self._b3.ask_json, prompt)
        return data if isinstance(data, dict) else {}
