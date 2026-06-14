from __future__ import annotations

import argparse
import json
import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_gigachat import GigaChat
from langgraph.graph import END, START, StateGraph

import llm_tool_rag_baseline as b1
from llm_tool_rag_baseline import ROOT, load_qa, retrieve_policy_docs
from langgraph_plan_validate_baseline import dump_draft, normalize_draft, parse_draft, validate


MAX_ROUNDS = 2
LLM = None
VALID_OUTCOMES = {"recommendation", "clarification", "escalation", "rejection", "info"}

# Общий порядок выбора исхода (по смыслу из корневого README, не из qa-кейсов).
OUTCOME_GUIDE = (
    "Выбор outcome_type — по порядку, бери первый подходящий:\n"
    "1. info — пользователь спрашивает только о правилах сервиса, без подбора поездки.\n"
    "2. escalation — нужна проверка документов/виз участника, либо пользователь просит подтвердить/"
    "оформить без обязательной проверки (требуется человек-оператор).\n"
    "3. recommendation — специалисты нашли допустимый вариант, удовлетворяющий жёсткие требования и "
    "бюджет. Это ПРИОРИТЕТНЫЙ исход, когда план найден: не понижай его до уточнения из осторожности.\n"
    "4. clarification — не хватает данных, либо требования конфликтуют/невыполнимы и возможен компромисс: "
    "спроси у пользователя недостающее или приоритет.\n"
    "5. rejection — пользователь явно запретил компромисс и выход за бюджет, а допустимого варианта нет.\n"
)


class CaseState(TypedDict):
    case: dict[str, Any]
    context: dict[str, Any]
    intent_analysis: dict[str, Any]
    flight_analysis: dict[str, Any]
    hotel_analysis: dict[str, Any]
    tour_analysis: dict[str, Any]
    policy_analysis: dict[str, Any]
    draft: dict[str, Any]
    raw: str
    feedback: str
    ok: bool
    rounds: int


def build_llm() -> GigaChat:
    load_dotenv(ROOT / ".env")
    credentials = os.getenv("GIGACHAT_CREDENTIALS")
    if not credentials:
        raise RuntimeError("GIGACHAT_CREDENTIALS не найден. Создай .env по .env.example.")
    return GigaChat(
        credentials=credentials,
        scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        model=os.getenv("GIGACHAT_MODEL", "GigaChat-2-Max"),
        verify_ssl_certs=False,
        temperature=0,
    )


def ask_json(prompt: str) -> dict[str, Any]:
    text = str(LLM.invoke([HumanMessage(content=prompt)]).content)
    return parse_draft(text)


def rows(table: str, **filters: str) -> list[dict[str, str]]:
    result = b1.TABLES[table]
    for key, value in filters.items():
        if value is not None:
            result = [row for row in result if row.get(key) == value]
    return result


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_context_node(state: CaseState) -> dict[str, Any]:
    case = state["case"]
    group = next((row for row in b1.TABLES["groups"] if row["group_id"] == case.get("group_id")), None)
    members = rows("members", group_id=case.get("group_id")) if group else []
    traveler_ids = {row["traveler_id"] for row in members}
    travelers = [row for row in b1.TABLES["travelers"] if row["traveler_id"] in traveler_ids]
    preferences = [row for row in b1.TABLES["preferences"] if row["traveler_id"] in traveler_ids]

    destination = group["destination"] if group else None
    origin = group["origin_city"] if group else None
    context = {
        "case": {
            "case_id": case["case_id"],
            "category": case["category"],
            "group_id": case.get("group_id"),
            "user_request": case["user_request"],
        },
        "group": group,
        "members": members,
        "travelers": travelers,
        "preferences": preferences,
        "flights": rows("flights", origin_city=origin, destination=destination) if group else [],
        "hotels": rows("hotels", destination=destination) if group else [],
        "tours": rows("tours", destination=destination) if group else [],
    }
    return {"context": context}


def intent_node(state: CaseState) -> dict[str, Any]:
    context = state["context"]
    prompt = (
        "Ты IntentAgent. Классифицируй запрос travel-пользователя до планирования. "
        "Верни только minified JSON.\n"
        "Схема: {\"request_type\":\"planning|replanning|info\","
        "\"expected_outcome_hint\":\"recommendation|clarification|escalation|rejection|info\","
        "\"constraint_mode\":\"flexible|strict|conflict\","
        "\"risk_level\":\"normal|requires_escalation\","
        "\"effective_budget_rub\":number|null,"
        "\"missing_fields\":[string],\"reason\":\"...\"}\n\n"
        "Правила:\n"
        "- Если пользователь называет бюджет прямо в запросе (напр. 'уложись в 160000', 'до 150 тысяч'), "
        "верни это число в effective_budget_rub — оно приоритетнее бюджета группы. Иначе null.\n"
        "- Если пользователь спрашивает только правило/условие сервиса, request_type=info и expected_outcome_hint=info.\n"
        "- risk_level=requires_escalation только когда решение нельзя принять автоматически и нужен "
        "человек-оператор (документы/визы участника, подтверждение без обязательной проверки); обычные "
        "ограничения и конфликты — это планирование, уточнение или отказ, не оператор.\n"
        "- Если пользователь просит изменить прошлый/тот же вариант, request_type=replanning.\n"
        + "\n" + OUTCOME_GUIDE + "\n"
        "- Если требования жёсткие и конфликтуют с бюджетом/данными, constraint_mode=conflict.\n"
        "- Если данных достаточно для конкретного варианта, не проси clarification только из осторожности.\n"
        f"Контекст: {compact(context)}"
    )
    return {"intent_analysis": ask_json(prompt)}


def flight_node(state: CaseState) -> dict[str, Any]:
    context = state["context"]
    intent = state["intent_analysis"]
    prompt = (
        "Ты FlightAgent. Проанализируй только перелёты и верни minified JSON.\n"
        "Схема: {\"recommended_flight_id\":string|null,\"acceptable_ids\":[string],"
        "\"risks\":[string],\"reason\":\"...\"}\n"
        "Учитывай город отправления, направление, багаж, пересадки, ранний вылет, ночной прилёт, детей и бюджет.\n"
        "Всегда заполняй recommended_flight_id лучшим доступным перелётом из context.flights; оговорки и "
        "риски клади в risks, но не оставляй recommended_flight_id пустым, если в данных есть хоть один перелёт.\n"
        f"Intent: {compact(intent)}\n"
        f"Контекст: {compact(context)}"
    )
    return {"flight_analysis": ask_json(prompt)}


def hotel_node(state: CaseState) -> dict[str, Any]:
    context = state["context"]
    intent = state["intent_analysis"]
    prompt = (
        "Ты HotelAgent. Проанализируй только отели и верни minified JSON.\n"
        "Схема: {\"recommended_hotel_id\":string|null,\"acceptable_ids\":[string],"
        "\"risks\":[string],\"reason\":\"...\"}\n"
        "Учитывай звёзды, завтрак, бесплатную отмену, рейтинг, цену за ночь, детей и бюджет.\n"
        "Всегда заполняй recommended_hotel_id лучшим доступным отелем из context.hotels; оговорки и риски "
        "клади в risks, но не оставляй recommended_hotel_id пустым, если в данных есть хоть один отель.\n"
        f"Intent: {compact(intent)}\n"
        f"Контекст: {compact(context)}"
    )
    return {"hotel_analysis": ask_json(prompt)}


def tour_node(state: CaseState) -> dict[str, Any]:
    context = state["context"]
    intent = state["intent_analysis"]
    prompt = (
        "Ты TourAgent. Проанализируй пакетные туры и верни minified JSON.\n"
        "Схема: {\"recommended_tour_id\":string|null,\"linked_hotel_id\":string|null,"
        "\"tour_is_preferred\":true|false,\"risks\":[string],\"reason\":\"...\"}\n"
        "Если запрос про пляжный отдых, туры, трансфер или готовый пакет, тур может быть предпочтительнее раздельной сборки.\n"
        f"Intent: {compact(intent)}\n"
        f"Контекст: {compact(context)}"
    )
    return {"tour_analysis": ask_json(prompt)}


def policy_node(state: CaseState) -> dict[str, Any]:
    context = state["context"]
    intent = state["intent_analysis"]
    docs = retrieve_policy_docs.invoke({"query": state["case"]["user_request"], "limit": 5})
    prompt = (
        "Ты PolicyAgent. По правилам сервиса определи применимые правила и реальные риски ИМЕННО для "
        "путешественников из context (учитывай их гражданство, возраст, направление). Верни minified JSON.\n"
        "Схема: {\"requires_escalation\":true|false,\"missing_info\":[string],"
        "\"hard_conflicts\":[string],\"relevant_rules\":[string],\"reason\":\"...\"}\n"
        "requires_escalation=true только когда решение нельзя безопасно принять автоматически и нужен "
        "человек-оператор: у конкретного участника есть реальный визовый/документный риск для направления, "
        "либо пользователь просит подтвердить/оформить без обязательной проверки. Назови в reason, кого и "
        "почему это касается. В остальных случаях requires_escalation=false.\n"
        f"Intent: {compact(intent)}\n"
        f"Запрос и контекст: {compact(context)}\n"
        f"Правила RAG: {docs}"
    )
    return {"policy_analysis": ask_json(prompt)}


def supervisor_node(state: CaseState) -> dict[str, Any]:
    case = state["case"]
    package = {
        "intent_analysis": state["intent_analysis"],
        "context": state["context"],
        "flight_analysis": state["flight_analysis"],
        "hotel_analysis": state["hotel_analysis"],
        "tour_analysis": state["tour_analysis"],
        "policy_analysis": state["policy_analysis"],
        "feedback": state["feedback"],
    }
    prompt = (
        "Ты Supervisor/Planner мультиагентной travel-системы. Собери финальное решение из structured state.\n"
        "Не придумывай id. Используй только id из context и анализов специалистов.\n"
        "Верни только minified JSON по схеме: "
        "{\"outcome_type\":\"recommendation|clarification|escalation|rejection|info\","
        "\"entities\":{\"flight_id\":null,\"hotel_id\":null,\"tour_id\":null},\"answer\":\"...\"}\n\n"
        + OUTCOME_GUIDE +
        "\nЭскалируй (escalation) только если policy_analysis.requires_escalation=true с конкретным "
        "обоснованием; иначе выбери исход среди recommendation/clarification/rejection по общему смыслу.\n"
        "Если intent_analysis.effective_budget_rub задан, он приоритетнее бюджета группы: если суммарная "
        "стоимость варианта его превышает, не давай recommendation — это clarification (или rejection, "
        "если пользователь прямо запретил компромисс и выход за бюджет).\n"
        "Если жёсткое требование пользователя нельзя выполнить по доступным данным, это не recommendation, "
        "а clarification (или rejection, если компромисс запрещён).\n"
        "Сначала учитывай intent_analysis.expected_outcome_hint. Отклоняйся от него только если "
        "специалисты нашли явное противоречие.\n"
        "Для replanning считай, что group/context описывает прошлый план и актуальные ограничения; "
        "если пользователь добавил новое условие, пересобери вариант, а не отказывайся без причины.\n"
        "Если выбран package tour, всё равно заполни связанные hotel_id и подходящий flight_id, когда они есть в данных.\n"
        f"Кейс: {compact({'category': case['category'], 'request': case['user_request']})}\n"
        f"Structured state: {compact(package)}"
    )
    raw = str(LLM.invoke([HumanMessage(content=prompt)]).content)
    draft = normalize_draft(case, parse_draft(raw), raw)
    return {"raw": dump_draft(draft) if draft else raw, "draft": draft, "rounds": state["rounds"] + 1}


def carry_entities(draft: dict[str, Any], state: CaseState) -> dict[str, Any]:
    """Переносим найденные специалистами id в entities ВСЕГДА — entity не зависит от outcome_type.
    Это сборка структурных результатов агентов (как normalize), а не решение."""
    if not isinstance(draft, dict):
        return draft
    ents = draft.get("entities")
    if not isinstance(ents, dict):
        ents = {}
    flight = state.get("flight_analysis") or {}
    hotel = state.get("hotel_analysis") or {}
    tour = state.get("tour_analysis") or {}

    def first_acceptable(analysis: dict[str, Any]) -> Any:
        ids = analysis.get("acceptable_ids")
        return ids[0] if isinstance(ids, list) and ids else None

    ents["flight_id"] = ents.get("flight_id") or flight.get("recommended_flight_id") or first_acceptable(flight)
    ents["hotel_id"] = (
        ents.get("hotel_id") or hotel.get("recommended_hotel_id")
        or tour.get("linked_hotel_id") or first_acceptable(hotel)
    )
    ents["tour_id"] = ents.get("tour_id") or tour.get("recommended_tour_id")
    draft["entities"] = ents
    return draft


def finalizer_node(state: CaseState) -> dict[str, Any]:
    case, draft = state["case"], state["draft"]
    intent = state["intent_analysis"]
    prompt = (
        "Ты FinalJsonAgent. Исправь только контракт финального ответа, сохрани смысл плана.\n"
        "outcome_type обязан быть одним из: recommendation, clarification, escalation, rejection, info.\n"
        "Верни только minified JSON по схеме: "
        "{\"outcome_type\":\"recommendation|clarification|escalation|rejection|info\","
        "\"entities\":{\"flight_id\":null,\"hotel_id\":null,\"tour_id\":null},\"answer\":\"...\"}\n"
        + OUTCOME_GUIDE +
        "\nПриведи outcome_type в соответствие с этим смыслом, сохранив план и id из черновика. "
        "Если intent.effective_budget_rub задан и стоимость плана его превышает, не оставляй recommendation "
        "(это clarification или rejection). "
        "Если intent_analysis.expected_outcome_hint не конфликтует с черновиком, используй его.\n"
        f"Intent: {compact(intent)}\n"
        f"Запрос: {case['user_request']}\n"
        f"Черновик: {dump_draft(draft) if draft else '(пусто)'}"
    )
    raw = str(LLM.invoke([HumanMessage(content=prompt)]).content)
    fixed = normalize_draft(case, parse_draft(raw), raw)
    if not fixed or fixed.get("outcome_type") not in VALID_OUTCOMES:
        fixed = draft if draft else {"outcome_type": "clarification", "entities": {}, "answer": ""}
        if fixed.get("outcome_type") not in VALID_OUTCOMES:
            fixed["outcome_type"] = "clarification"
    fixed = carry_entities(fixed, state)
    return {"raw": dump_draft(fixed), "draft": fixed}


def critic_node(state: CaseState) -> dict[str, Any]:
    case, draft = state["case"], state["draft"]
    violations = validate(case, draft)
    prompt = (
        "Ты CriticAgent. Проверь финальный ответ против запроса, structured state и нарушений.\n"
        "Верни только minified JSON: {\"ok\":true|false,\"feedback\":\"...\"}.\n"
        "ok=false только если ответ действительно надо переделать: неверный outcome_type, забыты id, "
        "нарушены ограничения, нужен escalation, но его нет, или выбран вариант не из данных.\n"
        "Не требуй escalation для обычного конфликта бюджета или предпочтений: это clarification/rejection.\n"
        "Если ответ рекомендует компромисс, который нарушает обязательное условие пользователя, ok=false.\n"
        f"Запрос: {case['user_request']}\n"
        f"Ответ: {dump_draft(draft) if draft else '(пусто)'}\n"
        f"Structured state: {compact({'intent': state['intent_analysis'], 'flight': state['flight_analysis'], 'hotel': state['hotel_analysis'], 'tour': state['tour_analysis'], 'policy': state['policy_analysis']})}\n"
        f"Детерминированные нарушения: {violations or 'нет'}"
    )
    verdict = ask_json(prompt)
    ok = bool(verdict.get("ok")) and not violations
    feedback = verdict.get("feedback") or ("; ".join(violations) if violations else "")
    return {"ok": ok, "feedback": feedback}


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
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("finalizer", finalizer_node)
    graph.add_node("critic", critic_node)
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "intent")
    graph.add_edge("intent", "flight")
    graph.add_edge("flight", "hotel")
    graph.add_edge("hotel", "tour")
    graph.add_edge("tour", "policy")
    graph.add_edge("policy", "supervisor")
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
            "draft": {},
            "raw": "",
            "feedback": "",
            "ok": False,
            "rounds": 0,
        }
    )
    return state["raw"]


def main() -> None:
    global LLM
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    qa = load_qa()
    b1.build_agent()
    LLM = build_llm()
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
