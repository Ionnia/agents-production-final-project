from __future__ import annotations

import argparse
import json
import re
from typing import Any, TypedDict

from langgraph.graph import START, END, StateGraph

# Final = entity-машинерия B3 (контекст + специалисты) + outcome, заземлённый ФАКТАМИ выполнимости.
# Детерминирован только калькулятор фактов (стоимость/бюджет/нарушения) — это инструмент, а не решение;
# тип исхода выбирают LLM-агенты (supervisor/critic) по этим фактам. Паттерн B2: грунт — tool, решение — агент.
import llm_tool_rag_baseline as b1
import mas_supervisor_baseline as b3
from mas_supervisor_baseline import (
    build_llm,
    ask_json,
    compact,
    carry_entities,
    OUTCOME_GUIDE,
    VALID_OUTCOMES,
    load_context_node,
    intent_node,
    flight_node,
    hotel_node,
    tour_node,
    policy_node,
)
from llm_tool_rag_baseline import load_qa
from langgraph_plan_validate_baseline import (
    dump_draft,
    lookup,
    get_group,
    nights,
    group_has_child,
    request_adds_child,
    safe_int,
)


MAX_ROUNDS = 2


class CaseState(TypedDict):
    case: dict[str, Any]
    context: dict[str, Any]
    intent_analysis: dict[str, Any]
    flight_analysis: dict[str, Any]
    hotel_analysis: dict[str, Any]
    tour_analysis: dict[str, Any]
    policy_analysis: dict[str, Any]
    feasibility: dict[str, Any]
    draft: dict[str, Any]
    raw: str
    feedback: str
    ok: bool
    rounds: int


def picks_from_specialists(state: CaseState) -> dict[str, Any]:
    """Те же id, что попадут в итоговые entities (см. carry_entities в B3): сначала
    recommended_*, затем acceptable_ids[0]. Иначе факты выполнимости считались бы для
    другого (или отсутствующего) плана, чем фактически эмитится в entities."""
    flight = state.get("flight_analysis") or {}
    hotel = state.get("hotel_analysis") or {}
    tour = state.get("tour_analysis") or {}

    def first_acceptable(analysis: dict[str, Any]) -> Any:
        ids = analysis.get("acceptable_ids")
        return ids[0] if isinstance(ids, list) and ids else None

    return {
        "flight_id": flight.get("recommended_flight_id") or first_acceptable(flight),
        "hotel_id": (
            hotel.get("recommended_hotel_id")
            or tour.get("linked_hotel_id") or first_acceptable(hotel)
        ),
        "tour_id": tour.get("recommended_tour_id"),
    }


def compute_feasibility(state: CaseState) -> dict[str, Any]:
    """Детерминированный калькулятор фактов (инструмент, не решение). Считает стоимость плана
    (без двойного счёта пакетного тура), бюджет (приоритет — бюджет из запроса), укладывается ли
    план в бюджет и структурные нарушения. Решение об исходе принимает агент по этим фактам."""
    case = state["case"]
    intent = state.get("intent_analysis") or {}
    picks = picks_from_specialists(state)
    flight = lookup("flights", "flight_id", picks.get("flight_id"))
    hotel = lookup("hotels", "hotel_id", picks.get("hotel_id"))
    tour = lookup("tours", "tour_id", picks.get("tour_id"))
    group = get_group(case.get("group_id"))
    n = nights(group) if group else None

    violations: list[str] = []
    if group:
        for label, row in (("перелёт", flight), ("отель", hotel), ("тур", tour)):
            if row and row.get("destination") and row["destination"] != group["destination"]:
                violations.append(f"{label} не совпадает с направлением группы {group['destination']}")

    # Стоимость без двойного счёта: пакетный тур уже включает перелёт/отель.
    total = 0
    if tour:
        total += safe_int(tour.get("total_price_rub")) or 0
        if flight and tour.get("includes_flight") != "1":
            total += safe_int(flight.get("price_rub")) or 0
        if hotel and tour.get("hotel_id") != hotel.get("hotel_id"):
            total += (safe_int(hotel.get("price_per_night_rub")) or 0) * (n or 1)
    else:
        if flight:
            total += safe_int(flight.get("price_rub")) or 0
        if hotel and n:
            total += (safe_int(hotel.get("price_per_night_rub")) or 0) * n

    eff = intent.get("effective_budget_rub")
    try:
        eff = int(eff) if eff not in (None, "") else None
    except (TypeError, ValueError):
        eff = None
    budget = eff if eff else (safe_int(group.get("budget_rub")) if group else None)
    within_budget = (total <= budget) if (budget and total) else None

    if flight and group and (group_has_child(group) or request_adds_child(case)):
        arrival = flight.get("arrival_time", "")
        hour = int(arrival[:2]) if re.match(r"^\d{2}:", arrival) else None
        # Ночной прилёт — после 23:00 (policy 02_baggage_and_fares.md §12) или раннее утро (<06:00).
        if hour is not None and (hour >= 23 or hour < 6):
            violations.append(f"ночной прилёт {arrival} для группы с ребёнком")

    # Атрибуты выбранного плана как ФАКТЫ — агент сам сверит их с жёсткими требованиями из запроса
    # (прямой рейс, категория отеля, багаж, завтрак, отмена). Перечень требований не зашит в код.
    chosen: dict[str, Any] = {}
    if flight:
        chosen["flight"] = {
            "stops": safe_int(flight.get("stops")),
            "direct": flight.get("stops") == "0",
            "baggage_included": flight.get("baggage_included") == "1",
            "arrival_time": flight.get("arrival_time"),
        }
    if hotel:
        chosen["hotel"] = {
            "stars": safe_int(hotel.get("stars")),
            "breakfast_included": hotel.get("breakfast_included") == "1",
            "free_cancellation": hotel.get("free_cancellation") == "1",
            "rating": hotel.get("rating"),
        }
    if tour:
        chosen["tour"] = {"includes_flight": tour["includes_flight"] == "1", "includes_transfer": tour["includes_transfer"] == "1"}

    return {
        "total_cost_rub": total or None,
        "effective_budget_rub": budget,
        "budget_source": "из запроса" if eff else "группы",
        "within_budget": within_budget,
        "structural_violations": violations,
        "chosen": chosen,
    }


def feasibility_node(state: CaseState) -> dict[str, Any]:
    return {"feasibility": compute_feasibility(state)}


def supervisor_node(state: CaseState) -> dict[str, Any]:
    case = state["case"]
    package = {
        "intent_analysis": state["intent_analysis"],
        "flight_analysis": state["flight_analysis"],
        "hotel_analysis": state["hotel_analysis"],
        "tour_analysis": state["tour_analysis"],
        "policy_analysis": state["policy_analysis"],
        "feasibility": state["feasibility"],
        "feedback": state["feedback"],
    }
    prompt = (
        "Ты Supervisor травел-агента. Прими решение из анализа специалистов и ФАКТОВ выполнимости. "
        "Не придумывай id — бери только из анализов специалистов.\n"
        + OUTCOME_GUIDE
        + "\nОпирайся на факты feasibility (бюджет и атрибуты посчитаны детерминированно, им можно доверять):\n"
        "- recommendation требует ОБОИХ: within_budget=true И выбранный план (chosen) удовлетворяет ВСЕ "
        "жёсткие требования пользователя из запроса. Сам сверь запрос с chosen: 'только прямой' → "
        "chosen.flight.direct=true; 'только 5*'/'не ниже 4*' → chosen.hotel.stars; нужен багаж/завтрак/"
        "отмена → соответствующие поля. structural_violations должны быть пусты.\n"
        "- если within_budget=false ИЛИ какое-то жёсткое требование не выполнено/конфликтует ИЛИ есть "
        "structural_violations: ПО УМОЛЧАНИЮ clarification — предложи компромисс или уточни приоритет. "
        "rejection ставь ТОЛЬКО если пользователь в запросе явно запретил любой компромисс.\n"
        "- escalation — только если policy_analysis.requires_escalation=true с конкретным обоснованием.\n"
        "Верни только minified JSON: "
        "{\"outcome_type\":\"recommendation|clarification|escalation|rejection|info\","
        "\"entities\":{\"flight_id\":null,\"hotel_id\":null,\"tour_id\":null},\"answer\":\"...\"}\n"
        f"Кейс: {compact({'category': case['category'], 'request': case['user_request']})}\n"
        f"State: {compact(package)}"
    )
    draft = carry_entities(ask_json(prompt), state)
    return {"raw": dump_draft(draft) if draft else "", "draft": draft, "rounds": state["rounds"] + 1}


def finalizer_node(state: CaseState) -> dict[str, Any]:
    case, draft = state["case"], state["draft"]
    prompt = (
        "Ты FinalJsonAgent. Приведи ответ к строгой схеме, сохранив план и id из черновика. "
        "outcome_type обязан быть одним из: recommendation, clarification, escalation, rejection, info.\n"
        + OUTCOME_GUIDE
        + "\nИспользуй факты feasibility как основу для outcome_type. Верни только minified JSON: "
        "{\"outcome_type\":\"recommendation|clarification|escalation|rejection|info\","
        "\"entities\":{\"flight_id\":null,\"hotel_id\":null,\"tour_id\":null},\"answer\":\"...\"}\n"
        f"Feasibility: {compact(state['feasibility'])}\n"
        f"Запрос: {case['user_request']}\n"
        f"Черновик: {dump_draft(draft) if draft else '(пусто)'}"
    )
    fixed = carry_entities(ask_json(prompt), state)
    if not fixed or fixed.get("outcome_type") not in VALID_OUTCOMES:
        fixed = draft if draft else {"outcome_type": "clarification", "entities": {}, "answer": ""}
        if fixed.get("outcome_type") not in VALID_OUTCOMES:
            fixed["outcome_type"] = "clarification"
        fixed = carry_entities(fixed, state)
    return {"raw": dump_draft(fixed), "draft": fixed}


def critic_node(state: CaseState) -> dict[str, Any]:
    """Критик заземляется на ФАКТЫ выполнимости (а не на детерминированный код): если факты и исход
    рассогласованы — отправляет на переделку."""
    case, draft = state["case"], state["draft"]
    prompt = (
        "Ты CriticAgent. Проверь, согласован ли итог с фактами выполнимости и запросом. "
        "Верни только minified JSON: {\"ok\":true|false,\"feedback\":\"...\"}.\n"
        "ok=false, если: within_budget=true, structural_violations пусты И выбранный план (chosen) "
        "удовлетворяет ВСЕ жёсткие требования пользователя, но outcome не recommendation; либо "
        "outcome=recommendation, хотя within_budget=false, есть structural_violations или какое-то "
        "жёсткое требование пользователя не выполнено (сверь запрос с chosen); либо outcome=rejection, "
        "хотя пользователь не запрещал компромисс (нужен clarification); либо забыты id, которые нашли "
        "специалисты; либо нужен escalation по policy, а его нет.\n"
        f"Факты feasibility: {compact(state['feasibility'])}\n"
        f"Policy: {compact(state['policy_analysis'])}\n"
        f"Запрос: {case['user_request']}\n"
        f"Ответ: {dump_draft(draft) if draft else '(пусто)'}"
    )
    verdict = ask_json(prompt)
    return {"ok": bool(verdict.get("ok")), "feedback": verdict.get("feedback") or ""}


def route(state: CaseState) -> str:
    if not state["ok"] and state["rounds"] < MAX_ROUNDS:
        return "supervisor"
    return "end"


def build_graph():
    graph = StateGraph(CaseState)
    graph.add_node("load_context", load_context_node)
    graph.add_node("intent", intent_node)
    graph.add_node("flight", flight_node)
    graph.add_node("hotel", hotel_node)
    graph.add_node("tour", tour_node)
    graph.add_node("policy", policy_node)
    graph.add_node("feasibility", feasibility_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("finalizer", finalizer_node)
    graph.add_node("critic", critic_node)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "intent")
    graph.add_edge("intent", "flight")
    graph.add_edge("flight", "hotel")
    graph.add_edge("hotel", "tour")
    graph.add_edge("tour", "policy")
    graph.add_edge("policy", "feasibility")
    graph.add_edge("feasibility", "supervisor")
    graph.add_edge("supervisor", "finalizer")
    graph.add_edge("finalizer", "critic")
    graph.add_conditional_edges("critic", route, {"supervisor": "supervisor", "end": END})
    return graph.compile()


def run_case(app, case: dict[str, Any]) -> str:
    state = app.invoke(
        {
            "case": case,
            "context": {},
            "intent_analysis": {},
            "flight_analysis": {},
            "hotel_analysis": {},
            "tour_analysis": {},
            "policy_analysis": {},
            "feasibility": {},
            "draft": {},
            "raw": "",
            "feedback": "",
            "ok": False,
            "rounds": 0,
        }
    )
    return state["raw"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    qa = load_qa()
    b1.build_agent()        # инициализирует policy RAG vectorstore
    b3.LLM = build_llm()    # переиспользуемые узлы B3 берут LLM из его модуля
    app = build_graph()

    if args.case_id:
        case = next(item for item in qa if item["case_id"] == args.case_id)
        print(run_case(app, case))
        return

    if args.all:
        for case in qa:
            try:
                prediction = run_case(app, case)
            except Exception as exc:  # один сбойный кейс (напр. сетевой/квота) не должен ронять весь прогон
                prediction = json.dumps(
                    {"outcome_type": "info", "entities": {}, "answer": f"ERROR: {exc}"},
                    ensure_ascii=False,
                )
            print(json.dumps({"case_id": case["case_id"], "prediction": prediction}, ensure_ascii=False), flush=True)
        return

    print("Укажи --case-id Q-001 или --all")


if __name__ == "__main__":
    main()
