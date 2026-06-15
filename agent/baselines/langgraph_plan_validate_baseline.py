from __future__ import annotations

import argparse
import json
import re
from datetime import date
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import START, END, StateGraph

from llm_tool_rag_baseline import TABLES, build_agent, load_qa


MAX_DRAFTS = 3  # первый черновик + до двух переплётов по результатам валидации
AGENT = None    # собирается один раз в main(), как POLICY_VECTORSTORE в B1


class CaseState(TypedDict):
    case: dict[str, Any]
    raw: str
    draft: dict[str, Any]
    violations: list[str]
    drafts: int


def safe_int(value: Any) -> int | None:
    """Толерантный int для CSV-полей: пустая/нечисловая ячейка не должна ронять узел графа."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def dump_draft(draft: dict[str, Any]) -> str:
    return json.dumps(draft, ensure_ascii=False, separators=(",", ":"))


def parse_draft(text: str) -> dict[str, Any]:
    """Толерантный разбор финального JSON-ответа агента."""
    # GigaChat иногда подставляет служебный токен <|superquote|> вместо кавычки;
    # нормализуем его так же, как оффлайн-оценщик (evaluate_predictions.parse_prediction),
    # иначе валидный по смыслу ответ распарсился бы в {} на рантайме.
    text = text.replace("<|superquote|>", '"')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def ids_in_text(text: str, prefix: str) -> list[str]:
    return sorted(set(re.findall(rf"\b{prefix}-\d+\b", text)))


def lookup(table: str, id_key: str, value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    return next((row for row in TABLES[table] if row[id_key] == value), None)


def get_group(group_id: str | None) -> dict[str, Any] | None:
    if not group_id:
        return None
    return next((g for g in TABLES["groups"] if g["group_id"] == group_id), None)


def group_preferences(group: dict[str, Any]) -> list[dict[str, Any]]:
    members = [m for m in TABLES["members"] if m["group_id"] == group["group_id"]]
    traveler_ids = {m["traveler_id"] for m in members}
    return [p for p in TABLES["preferences"] if p["traveler_id"] in traveler_ids]


def group_has_child(group: dict[str, Any]) -> bool:
    members = [m for m in TABLES["members"] if m["group_id"] == group["group_id"]]
    if any(m.get("role_in_group", "").lower() == "child" for m in members):
        return True
    comment = group.get("group_comment", "").lower()
    return "ребёнок" in comment or "ребенок" in comment


def request_adds_child(case: dict[str, Any]) -> bool:
    request = case.get("user_request", "").lower()
    return "ребён" in request or "ребен" in request


def nights(group: dict[str, Any]) -> int | None:
    try:
        start = date.fromisoformat(group["start_date"])
        end = date.fromisoformat(group["end_date"])
        return max((end - start).days, 1)
    except (KeyError, ValueError):
        return None


def best_flight_for_group(group: dict[str, Any], case: dict[str, Any]) -> str | None:
    rows = [
        row
        for row in TABLES["flights"]
        if row["origin_city"] == group["origin_city"] and row["destination"] == group["destination"]
    ]
    if not rows:
        return None

    text = (group.get("group_comment", "") + " " + case.get("user_request", "")).lower()
    prefs = group_preferences(group)
    prefer_direct = "прям" in text or any(p["preference_type"] == "flight" and p["preference_value"] == "direct" for p in prefs)
    prefer_budget = "бюджет" in text or "дешев" in text or "сократ" in text
    need_baggage = "багаж" in text or any(p["preference_type"] == "baggage" and p["preference_value"] == "included" for p in prefs)
    avoid_early = "ранн" in text or any(p["preference_type"] == "departure_time" for p in prefs)
    has_child = group_has_child(group) or request_adds_child(case)

    def score(row: dict[str, str]) -> tuple[int, int]:
        points = 0
        stops = safe_int(row.get("stops"))
        price = safe_int(row.get("price_rub"))
        departure_hour = safe_int(row.get("departure_time", "")[:2])
        arrival_hour = safe_int(row.get("arrival_time", "")[:2])
        if prefer_direct and stops == 0:
            points += 80
        if need_baggage and row["baggage_included"] == "1":
            points += 60
        if avoid_early and departure_hour is not None and departure_hour < 6:
            points -= 60
        if has_child and arrival_hour is not None and (arrival_hour >= 23 or arrival_hour < 6):
            points -= 100
        if prefer_budget:
            points -= (price or 0) // 1000
        else:
            points -= (stops or 0) * 25
            points -= (price or 0) // 5000
        return points, -(price or 0)

    return max(rows, key=score)["flight_id"]


def normalize_draft(case: dict[str, Any], draft: dict[str, Any], raw: str) -> dict[str, Any]:
    if not draft:
        return draft

    entities = draft.get("entities")
    if not isinstance(entities, dict):
        entities = {}
    for key in ("flight_id", "hotel_id", "tour_id"):
        entities.setdefault(key, None)

    for value in ids_in_text(raw, "FL"):
        entities["flight_id"] = entities.get("flight_id") or value
    for value in ids_in_text(raw, "HT"):
        entities["hotel_id"] = entities.get("hotel_id") or value
    for value in ids_in_text(raw, "TR"):
        entities["tour_id"] = entities.get("tour_id") or value

    tour = lookup("tours", "tour_id", entities.get("tour_id"))
    group = get_group(case.get("group_id"))
    if tour:
        entities["hotel_id"] = entities.get("hotel_id") or tour.get("hotel_id")
        if group and tour.get("includes_flight") == "1":
            entities["flight_id"] = entities.get("flight_id") or best_flight_for_group(group, case)

    if draft.get("outcome_type") == "escalation" and not entities.get("tour_id"):
        request = case.get("user_request", "").lower()
        if group and "тур" in request:
            tour = next((row for row in TABLES["tours"] if row["destination"] == group["destination"]), None)
            if tour:
                entities["tour_id"] = tour["tour_id"]

    draft["entities"] = entities
    return draft


def validate(case: dict[str, Any], draft: dict[str, Any]) -> list[str]:
    """Инструмент валидации плана (детерминированный, локальный стаб backend-контракта
    `POST /internal/plans/validate`): считает бюджет и проверяет жёсткие ограничения по
    реальным данным. Это guardrail/калькулятор, а не рефлексия агента — суждение о том,
    что делать с нарушениями, принимает LLM на переплёте (узел `draft`)."""
    violations: list[str] = []
    if not draft:
        return ["ответ не является валидным JSON — верни только minified JSON"]

    if draft.get("outcome_type") not in {"recommendation", "clarification", "escalation", "rejection", "info"}:
        violations.append("outcome_type отсутствует или имеет недопустимое значение")

    entities = draft.get("entities") or {}
    if not isinstance(entities, dict):
        violations.append("entities должен быть объектом")
        entities = {}

    flight = lookup("flights", "flight_id", entities.get("flight_id"))
    hotel = lookup("hotels", "hotel_id", entities.get("hotel_id"))
    tour = lookup("tours", "tour_id", entities.get("tour_id"))

    for key, row in (("flight_id", flight), ("hotel_id", hotel), ("tour_id", tour)):
        value = entities.get(key)
        if value and row is None:
            violations.append(f"{key}={value} нет в данных — выбери id из tools")

    group = get_group(case.get("group_id"))
    if group:
        if flight and flight["destination"] != group["destination"]:
            violations.append(f"flight_id={flight['flight_id']} не совпадает с направлением группы {group['destination']}")
        if hotel and hotel["destination"] != group["destination"]:
            violations.append(f"hotel_id={hotel['hotel_id']} не совпадает с направлением группы {group['destination']}")
        if tour and tour["destination"] != group["destination"]:
            violations.append(f"tour_id={tour['tour_id']} не совпадает с направлением группы {group['destination']}")

    if tour and tour.get("hotel_id") and not entities.get("hotel_id"):
        violations.append(f"tour_id={tour['tour_id']} связан с hotel_id={tour['hotel_id']} — добавь hotel_id в entities")
    if tour and tour.get("includes_flight") == "1" and group and not entities.get("flight_id"):
        violations.append(f"tour_id={tour['tour_id']} включает перелёт — добавь подходящий flight_id в entities")

    if draft.get("outcome_type") != "recommendation":
        return violations

    if not group:
        return violations

    n = nights(group)
    total = 0
    if flight:
        total += safe_int(flight.get("price_rub")) or 0
    if hotel and n:
        total += (safe_int(hotel.get("price_per_night_rub")) or 0) * n
    if tour:
        total += safe_int(tour.get("total_price_rub")) or 0

    budget = safe_int(group.get("budget_rub"))
    if budget and total and total > budget:
        violations.append(f"итог {total} ₽ превышает бюджет {budget} ₽")

    if flight and (group_has_child(group) or request_adds_child(case)):
        arrival = flight.get("arrival_time", "")
        hour = int(arrival[:2]) if re.match(r"^\d{2}:", arrival) else None
        # Ночной прилёт — после 23:00 (policy 02_baggage_and_fares.md §12) или раннее утро (<06:00).
        if hour is not None and (hour >= 23 or hour < 6):
            violations.append(f"ночной прилёт {arrival} недопустим для группы с ребёнком")

    return violations


def draft_node(state: CaseState) -> dict[str, Any]:
    case = state["case"]
    payload = {
        "case_id": case["case_id"],
        "category": case["category"],
        "group_id": case.get("group_id"),
        "user_request": case["user_request"],
    }
    content = (
        "Реши кейс. Используй tools перед финальным ответом.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    if state["violations"]:
        content += (
            "\n\nПредыдущий черновик нарушает требования:\n"
            + "\n".join(f"- {v}" for v in state["violations"])
            + "\n\nИсправь: подбери другие flight/hotel/tour из tools. "
            "Если уложиться в бюджет и ограничения нельзя — верни rejection; "
            "если не хватает данных — верни clarification. Снова верни minified JSON."
        )

    result = AGENT.invoke({"messages": [HumanMessage(content=content)]})
    raw = str(result["messages"][-1].content)
    draft = normalize_draft(case, parse_draft(raw), raw)
    return {"raw": dump_draft(draft) if draft else raw, "draft": draft, "drafts": state["drafts"] + 1}


def validate_node(state: CaseState) -> dict[str, Any]:
    return {"violations": validate(state["case"], state["draft"])}


def route(state: CaseState) -> str:
    if state["violations"] and state["drafts"] < MAX_DRAFTS:
        return "draft"
    return "end"


def build_graph():
    graph = StateGraph(CaseState)
    graph.add_node("draft", draft_node)
    graph.add_node("validate", validate_node)
    graph.add_edge(START, "draft")
    graph.add_edge("draft", "validate")
    graph.add_conditional_edges("validate", route, {"draft": "draft", "end": END})
    return graph.compile()


def run_case(app, case: dict[str, Any]) -> str:
    state = app.invoke(
        {"case": case, "raw": "", "draft": {}, "violations": [], "drafts": 0}
    )
    return state["raw"]


def main() -> None:
    global AGENT
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    qa = load_qa()
    AGENT = build_agent()
    app = build_graph()

    if args.case_id:
        case = next(item for item in qa if item["case_id"] == args.case_id)
        print(run_case(app, case))
        return

    if args.all:
        for case in qa:
            print(json.dumps({"case_id": case["case_id"], "prediction": run_case(app, case)}, ensure_ascii=False))
        return

    print("Укажи --case-id Q-001 или --all")


if __name__ == "__main__":
    main()
