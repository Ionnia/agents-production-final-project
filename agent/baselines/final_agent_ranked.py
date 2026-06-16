from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date
from typing import Any, TypedDict

from langgraph.graph import START, END, StateGraph

import llm_tool_rag_baseline as b1
import mas_supervisor_baseline as b3
import travel_catalog as cat
from mas_supervisor_baseline import (
    ask_json,
    compact,
    carry_entities,
    OUTCOME_GUIDE,
    VALID_OUTCOMES,
    intent_node,
    flight_node,
    hotel_node,
    tour_node,
    policy_node,
    rows,
)
from llm_tool_rag_baseline import load_qa, retrieve_policy_docs
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
    resolve: dict[str, Any]
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


# ── Conversation-aware resolution (направление / город вылета / даты / бюджет) ───────────────────

def _compute_nights(start: str | None, end: str | None) -> int | None:
    try:
        if not start or not end:
            return None
        return max((date.fromisoformat(end) - date.fromisoformat(start)).days, 1)
    except ValueError:
        return None


def _extract_trip_facts(dialog: str) -> dict[str, Any]:
    """LLM-извлечение дат/бюджета/состава из всей переписки. Толерантно к пропускам
    (всё может быть null). Бюджет нормализуется в РУБЛИ; явные евро/доллары пересчитываются."""
    prompt = (
        "Извлеки факты поездки из переписки. Верни только minified JSON по схеме:\n"
        "{\"start_date\":\"YYYY-MM-DD|null\",\"end_date\":\"YYYY-MM-DD|null\","
        "\"budget_rub\":number|null,\"adults\":number|null,\"children\":number|null}\n"
        "Правила:\n"
        "- Даты выводи в ISO. Если год не указан, считай ближайший подходящий (2026).\n"
        "- budget_rub ВСЕГДА в рублях. Если бюджет назван в евро — умножь на 100, в долларах — на 90. "
        "Если бюджет указан 'на человека', умножь на число путешественников. Иначе null.\n"
        "- adults/children — число взрослых/детей, если названо; иначе null.\n"
        f"Переписка: {compact(dialog)}"
    )
    try:
        data = ask_json(prompt)
    except Exception:  # noqa: BLE001 — извлечение фактов не должно ронять граф
        return {}
    if not isinstance(data, dict):
        return {}
    budget = safe_int(data.get("budget_rub"))
    # Защита от типичной ошибки парсинга валюты: ни одно реальное направление в наборе
    # не дешевле ~30к ₽, поэтому подозрительно малый бюджет считаем не распознанным.
    if budget is not None and budget < 30000:
        budget = None
    return {
        "start_date": data.get("start_date") if isinstance(data.get("start_date"), str) else None,
        "end_date": data.get("end_date") if isinstance(data.get("end_date"), str) else None,
        "budget_rub": budget,
        "adults": safe_int(data.get("adults")),
        "children": safe_int(data.get("children")),
    }


def _has_any_destination_mention(text: str) -> bool:
    low = (text or "").lower()
    aliases: list[str] = []
    for entry in cat.DESTINATION_CATALOG.values():
        aliases.extend(entry["city_aliases"])
        aliases.extend(entry["country_aliases"])
    aliases.extend(
        [
            "греция", "грецию", "италия", "италию", "рим", "франция", "францию",
            "париж", "лондон", "мексика", "мексику", "вьетнам", "вьетнам",
            "бали", "мальдивы", "мальдив", "кипр", "египет", "египет",
        ]
    )
    return any(alias in low for alias in aliases)


def _conversation_kind(text: str) -> str:
    """Классификация намерения реплики через LLM (минимум детерминизма).
    Детерминированный keyword-классификатор остаётся ТОЛЬКО как fallback — если LLM недоступен
    или вернул мусор, граф не должен падать."""
    if not (text or "").strip():
        return "out_of_scope"
    prompt = (
        "Классифицируй сообщение пользователя travel-сервиса в РОВНО одну категорию. "
        "Верни только minified JSON: {\"kind\":\"travel|policy_info|smalltalk|out_of_scope\"}.\n"
        "- travel: пользователь хочет, чтобы ему ПОДОБРАЛИ или ИЗМЕНИЛИ конкретную поездку — есть "
        "намерение ехать (называет направление/даты/бюджет/состав, 'подбери', 'хочу поехать', в т.ч. "
        "косвенно 'хочется к морю', 'надо уехать к солнцу'). Если намерения ехать нет — это НЕ travel.\n"
        "- policy_info: ИНФОРМАЦИОННЫЙ вопрос без просьбы подобрать поездку — про правила сервиса "
        "(отмена, багаж, тарифы, ночной прилёт, документы/визы), А ТАКЖЕ общие вопросы-советы и "
        "сравнения ('что лучше', 'всегда ли … лучше', 'в чём разница', 'стоит ли', 'чем отличается') "
        "про туры/отели/перелёты. Упоминание слов тур/отель/рейс само по себе НЕ делает запрос travel, "
        "если нет намерения подобрать конкретную поездку.\n"
        "- smalltalk: приветствие, благодарность, болтовня без задачи.\n"
        "- out_of_scope: тема не про путешествия и не про правила сервиса.\n"
        f"Сообщение: {compact(text)}"
    )
    try:
        data = ask_json(prompt)
        kind = data.get("kind") if isinstance(data, dict) else None
        if kind in {"travel", "policy_info", "smalltalk", "out_of_scope"}:
            return kind
    except Exception:  # noqa: BLE001 — классификация не должна ронять граф
        pass
    return _conversation_kind_keywords(text)


def _conversation_kind_keywords(text: str) -> str:
    """Детерминированный fallback-классификатор (используется только при сбое LLM)."""
    low = (text or "").lower().strip()
    info_markers = [
        "можно ли", "что считается", "что входит", "всегда ли", "как вы", "какие правила",
        "условия", "отмен", "бронирован", "ночным прил", "пакетный тур лучше",
        "чем отдельно", "правил", "документ", "виз",
    ]
    planning_markers = [
        "подбери", "подберите", "хочу", "нужна поездка", "нужен", "сделай",
        "пересчитай", "пересобери", "оставь", "добавь",
    ]
    if any(marker in low for marker in info_markers) and not any(marker in low for marker in planning_markers):
        return "policy_info"
    travel_markers = [
        "поезд", "путеше", "тур", "отел", "перел", "рейс", "билет", "вылет",
        "маршрут", "отпуск", "багаж", "завтрак", "бюджет", "руб", "дата",
        "ноч", "море", "пляж", "страхов", "виза", "документ", "аэропорт",
    ]
    if any(marker in low for marker in travel_markers) or _has_any_destination_mention(low) or cat.match_origin(low):
        return "travel"
    smalltalk_patterns = [
        r"^(привет|здравствуй|здравствуйте|добрый день|доброе утро|добрый вечер)[\s!,.?]*$",
        r"^(привет|здравствуй|здравствуйте)[\s!,.?]+(как дела|как ты|что нового)[\s!,.?]*$",
        r"^(как дела|как ты|что нового)[\s!,.?]*$",
        r"^(спасибо|благодарю|ок|окей|понял|поняла)[\s!,.?]*$",
    ]
    if any(re.match(pattern, low) for pattern in smalltalk_patterns):
        return "smalltalk"
    return "out_of_scope"


def direct_info_node(state: CaseState) -> dict[str, Any]:
    kind = state["resolve"].get("kind")
    if kind == "smalltalk":
        answer = (
            "Привет! Всё хорошо, спасибо. Я помогу подобрать поездку: направление, "
            "перелёт, отель, тур и ограничения по бюджету или предпочтениям."
        )
    else:
        answer = (
            "Я специализируюсь на планировании путешествий. Напишите, куда хотите "
            "поехать, откуда вылетаете, даты, бюджет и важные пожелания."
        )
    draft = {"outcome_type": "info", "entities": {}, "answer": answer}
    return {"raw": dump_draft(draft), "draft": draft, "rounds": state["rounds"] + 1, "ok": True}


def policy_info_node(state: CaseState) -> dict[str, Any]:
    request = state["case"].get("user_request", "")
    docs = retrieve_policy_docs.invoke({"query": request, "limit": 5})
    prompt = (
        "Ты PolicyQAAgent. Ответь на информационный вопрос пользователя по правилам travel-сервиса. "
        "Не подбирай поездку, не проси направление, не выбирай flight_id/hotel_id/tour_id. "
        "Если вопрос касается риска документов/виз или оформления без проверки, аккуратно скажи, "
        "что нужна ручная проверка. Верни только minified JSON: "
        "{\"outcome_type\":\"info\",\"entities\":{\"flight_id\":null,\"hotel_id\":null,\"tour_id\":null},"
        "\"options\":[],\"answer\":\"...\"}\n"
        f"Вопрос: {request}\n"
        f"Правила RAG: {docs}"
    )
    draft = ask_json(prompt)
    if not isinstance(draft, dict):
        draft = {}
    draft["outcome_type"] = "info"
    draft["entities"] = {"flight_id": None, "hotel_id": None, "tour_id": None}
    draft.setdefault("options", [])
    draft.setdefault("answer", "Я могу ответить на вопросы по правилам сервиса и подбору путешествий.")
    return {"raw": dump_draft(draft), "draft": draft, "rounds": state["rounds"] + 1, "ok": True}


def resolve_node(state: CaseState) -> dict[str, Any]:
    case = state["case"]
    # Group path (QA-кейсы и явный выбор группы) — направление/состав берём из группы как раньше.
    if case.get("group_id"):
        return {"resolve": {"group": True}}

    available = cat.available_codes(b1.TABLES)
    user_text = case.get("user_text_only") or case.get("user_request") or ""
    kind = _conversation_kind(user_text)
    if kind != "travel":
        return {"resolve": {"group": False, "kind": kind, "available": available}}
    dest_codes = cat.match_destinations(user_text, available)
    origin = cat.match_origin(user_text)
    dest_code = dest_codes[0] if len(dest_codes) == 1 else None
    # Извлекаем даты/бюджет только когда реально продолжаем к подбору — на ветке уточнения
    # (нет направления/города вылета) лишний LLM-вызов не нужен.
    facts = _extract_trip_facts(case.get("user_request") or user_text) if (dest_code and origin) else {}
    nights_n = _compute_nights(facts.get("start_date"), facts.get("end_date"))
    resolved: dict[str, Any] = {
        "group": False,
        "kind": "travel",
        "available": available,
        "has_destination_mention": _has_any_destination_mention(user_text),
        "dest_codes": dest_codes,
        "dest_code": dest_code,
        "origin": origin,
        "start_date": facts.get("start_date"),
        "end_date": facts.get("end_date"),
        "nights": nights_n,
        "budget_rub": facts.get("budget_rub"),
        "adults": facts.get("adults"),
        "children": facts.get("children"),
    }
    return {"resolve": resolved}


def route_resolve(state: CaseState) -> str:
    case = state["case"]
    if case.get("group_id"):
        return "load_context"
    resolved = state["resolve"]
    if resolved.get("kind") == "policy_info":
        return "policy_info"
    if resolved.get("kind") in {"smalltalk", "out_of_scope"}:
        return "direct_info"
    if resolved.get("dest_code") and resolved.get("origin"):
        return "load_context"
    return "clarify"


def clarify_node(state: CaseState) -> dict[str, Any]:
    """Детерминированный уточняющий вопрос С ВАРИАНТАМИ для каталожной части (направление/вылет).
    Свободный ввод по-прежнему разрешён downstream (allow_freeform=true в SSE)."""
    resolved = state["resolve"]
    dest_codes = resolved.get("dest_codes") or []
    available = resolved.get("available") or cat.available_codes(b1.TABLES)

    if not dest_codes and resolved.get("has_destination_mention"):
        options = [item["label"] for item in cat.destination_options(available)]
        answer = (
            "К сожалению, по этому направлению у меня сейчас нет предложений. "
            "Я могу подобрать поездку по одному из доступных направлений — выберите подходящее:"
        )
    elif not dest_codes:
        options = [item["label"] for item in cat.destination_options(available)]
        answer = "Куда хотите поехать? Могу подобрать поездку по одному из доступных направлений:"
    elif len(dest_codes) > 1:
        options = [cat.label_for_code(code) for code in dest_codes]
        answer = "Уточните, пожалуйста, какой именно город интересует:"
    else:
        # направление есть, не хватает города вылета
        options = [item["label"] for item in cat.origin_options()]
        answer = (
            f"Подбираю поездку в «{cat.city_for_code(resolved.get('dest_code'))}». "
            "Из какого города вылетаете?"
        )

    draft = {"outcome_type": "clarification", "entities": {}, "answer": answer, "options": options}
    return {"raw": dump_draft(draft), "draft": draft, "rounds": state["rounds"] + 1, "ok": True}


# ── Context (group ИЛИ извлечённое направление) ─────────────────────────────────────────────────

def _backend_context(case: dict[str, Any]) -> dict[str, Any]:
    value = case.get("backend_context")
    return value if isinstance(value, dict) else {}


def _table_from_context(state: CaseState, table: str) -> list[dict[str, str]]:
    context = state.get("context") or {}
    rows_ = context.get(table)
    return rows_ if isinstance(rows_, list) else []


def _lookup_context(state: CaseState, table: str, key: str, value: Any) -> dict[str, str] | None:
    if not value:
        return None
    for row in _table_from_context(state, table):
        if row.get(key) == value:
            return row
    return lookup(table, key, value)


def _truthy_flag(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes", "да"}


def _constraint_text(state: CaseState) -> str:
    context = state.get("context") or {}
    group = context.get("group") or {}
    parts = [
        state["case"].get("user_request", ""),
        group.get("group_comment", ""),
        group.get("comment", ""),
    ]
    return " ".join(str(part).lower() for part in parts if part)


def _group_pref_pairs(state: CaseState) -> set[tuple[str | None, str | None]]:
    return {
        (pref.get("preference_type") or pref.get("type"), pref.get("preference_value") or pref.get("value"))
        for pref in (state.get("context") or {}).get("preferences", [])
        if isinstance(pref, dict)
    }


def _hour(value: Any) -> int | None:
    text = str(value or "")
    return int(text[:2]) if re.match(r"^\d{2}:", text) else None


def _best_flight_from_context(state: CaseState) -> str | None:
    text = _constraint_text(state)
    prefs = _group_pref_pairs(state)
    rows_ = _table_from_context(state, "flights")
    if not rows_:
        return None

    required_baggage = "багаж" in text or ("baggage", "included") in prefs
    avoid_early = (
        "ранний вылет" in text
        or "раннего вылета" in text
        or ("departure_time", "daytime") in prefs
        or ("departure_time", "avoid_early_departure") in prefs
    )
    avoid_night = "ночн" in text or group_has_child((state.get("context") or {}).get("group"))
    require_direct = "только прям" in text or "прямой рейс" in text

    candidates = []
    for row in rows_:
        departure_hour = _hour(row.get("departure_time"))
        arrival_hour = _hour(row.get("arrival_time"))
        if required_baggage and not _truthy_flag(row.get("baggage_included")):
            continue
        if avoid_early and departure_hour is not None and departure_hour < 6:
            continue
        if avoid_night and arrival_hour is not None and (arrival_hour >= 23 or arrival_hour < 6):
            continue
        if require_direct and safe_int(row.get("stops")) not in (0, None):
            continue
        candidates.append(row)

    pool = candidates or rows_
    return min(
        pool,
        key=lambda row: (
            safe_int(row.get("price_rub")) or 10**12,
            safe_int(row.get("stops")) or 0,
        ),
    ).get("flight_id")


def _best_hotel_from_context(state: CaseState) -> str | None:
    text = _constraint_text(state)
    prefs = _group_pref_pairs(state)
    rows_ = _table_from_context(state, "hotels")
    if not rows_:
        return None

    min_stars = 5 if ("только 5" in text or "5*" in text or "5 зв" in text) else None
    breakfast = "завтрак" in text or ("meal", "breakfast") in prefs
    free_cancel = ("бесплатн" in text and "отмен" in text) or ("cancellation", "free") in prefs

    candidates = []
    for row in rows_:
        if min_stars and (safe_int(row.get("stars")) or 0) < min_stars:
            continue
        if breakfast and not _truthy_flag(row.get("breakfast_included")):
            continue
        if free_cancel and not _truthy_flag(row.get("free_cancellation")):
            continue
        candidates.append(row)

    pool = candidates or rows_
    return min(
        pool,
        key=lambda row: (
            safe_int(row.get("price_per_night_rub")) or 10**12,
            -(float(row.get("rating") or 0)),
        ),
    ).get("hotel_id")


def _ranked_ids(analysis: dict[str, Any], key: str) -> list[str]:
    ranked = analysis.get("ranked_candidates")
    result: list[str] = []
    if isinstance(ranked, list):
        for item in ranked:
            value = item.get(key) if isinstance(item, dict) else item
            if isinstance(value, str) and value and value not in result:
                result.append(value)
    recommended = analysis.get(f"recommended_{key}")
    if isinstance(recommended, str) and recommended and recommended not in result:
        result.append(recommended)
    acceptable = analysis.get("acceptable_ids")
    if isinstance(acceptable, list):
        for value in acceptable:
            if isinstance(value, str) and value and value not in result:
                result.append(value)
    return result


def _context_ids(state: CaseState, table: str, key: str) -> set[str]:
    return {
        row[key]
        for row in _table_from_context(state, table)
        if isinstance(row, dict) and isinstance(row.get(key), str)
    }


def _first_existing_ranked(state: CaseState, table: str, key: str, ids: list[str]) -> str | None:
    existing = _context_ids(state, table, key)
    for value in ids:
        if value in existing:
            return value
    return None


def flight_node(state: CaseState) -> dict[str, Any]:
    context = state["context"]
    intent = state["intent_analysis"]
    prompt = (
        "Ты FlightAgent. Проанализируй только перелёты и верни minified JSON.\n"
        "Схема: {\"recommended_flight_id\":string|null,"
        "\"ranked_candidates\":[{\"flight_id\":string,\"score\":number,\"reason\":\"...\"}],"
        "\"acceptable_ids\":[string],\"risks\":[string],\"reason\":\"...\"}\n"
        "Сначала сформируй ranked_candidates: отсортируй реальные context.flights от лучшего к худшему "
        "по соответствию запросу, ограничениям, багажу, пересадкам, времени, детям и цене. "
        "recommended_flight_id должен быть первым id из ranked_candidates. Не придумывай id.\n"
        f"Intent: {compact(intent)}\n"
        f"Контекст: {compact(context)}"
    )
    return {"flight_analysis": ask_json(prompt)}


def hotel_node(state: CaseState) -> dict[str, Any]:
    context = state["context"]
    intent = state["intent_analysis"]
    prompt = (
        "Ты HotelAgent. Проанализируй только отели и верни minified JSON.\n"
        "Схема: {\"recommended_hotel_id\":string|null,"
        "\"ranked_candidates\":[{\"hotel_id\":string,\"score\":number,\"reason\":\"...\"}],"
        "\"acceptable_ids\":[string],\"risks\":[string],\"reason\":\"...\"}\n"
        "Сначала сформируй ranked_candidates: отсортируй реальные context.hotels от лучшего к худшему.\n"
        "Стратегия ранжирования:\n"
        "1. Сначала отфильтруй обязательные требования пользователя и preferences: минимальный класс отеля, "
        "завтрак, бесплатная отмена, размещение детей, локация/стиль, если они явно есть.\n"
        "2. Если несколько отелей удовлетворяют обязательным требованиям, выбирай cost-efficient fit: "
        "более дешёвый подходящий вариант выше более дорогого premium-варианта.\n"
        "3. 5* или самый высокий рейтинг ставь первым только если пользователь явно просит premium/люкс/5*, "
        "максимальный комфорт или лучший рейтинг. Если в preferences указано 4plus, это значит 4* и выше, "
        "а не обязательный выбор 5*.\n"
        "4. Держи дорогой premium-вариант в ranked_candidates как альтернативу, но не делай его "
        "recommended_hotel_id без явного premium-запроса.\n"
        "recommended_hotel_id должен быть первым id из ranked_candidates. Не придумывай id.\n"
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
        "\"ranked_candidates\":[{\"tour_id\":string,\"score\":number,\"reason\":\"...\"}],"
        "\"tour_is_preferred\":true|false,\"risks\":[string],\"reason\":\"...\"}\n"
        "Если запрос про пляжный отдых, трансфер или готовый пакет, тур может быть предпочтительнее "
        "раздельной сборки. ranked_candidates сортируй только из реальных context.tours. Не придумывай id.\n"
        f"Intent: {compact(intent)}\n"
        f"Контекст: {compact(context)}"
    )
    return {"tour_analysis": ask_json(prompt)}


def load_context_node(state: CaseState) -> dict[str, Any]:
    case = state["case"]
    resolved = state.get("resolve") or {}
    backend = _backend_context(case)
    group = backend.get("group") or next(
        (row for row in b1.TABLES["groups"] if row["group_id"] == case.get("group_id")),
        None,
    )

    if group:
        members = backend.get("members") or rows("members", group_id=case.get("group_id"))
        traveler_ids = {row["traveler_id"] for row in members if row.get("traveler_id")}
        travelers = backend.get("travelers") or [
            row for row in b1.TABLES["travelers"] if row["traveler_id"] in traveler_ids
        ]
        preferences = backend.get("preferences") or [
            row for row in b1.TABLES["preferences"] if row["traveler_id"] in traveler_ids
        ]
        origin = group["origin_city"]
        destination = group["destination"]
    else:
        members, travelers, preferences = [], [], []
        origin = resolved.get("origin")
        destination = resolved.get("dest_code")

    # Human-readable labels on BOTH paths (group destination/origin are dataset codes like
    # "IST"/"Moscow"); the catalogue maps them to "Стамбул"/"Москва" so the plan card never
    # shows an airport code. Unknown values fall back to themselves.
    resolved_view = {
        "origin_city": cat.origin_label(origin),
        "origin_code": origin,
        "destination_code": destination,
        "destination_label": cat.city_for_code(destination),
        "start_date": (group["start_date"] if group else resolved.get("start_date")),
        "end_date": (group["end_date"] if group else resolved.get("end_date")),
        "budget_rub": (safe_int(group.get("budget_rub")) if group else resolved.get("budget_rub")),
    }
    context = {
        "case": {
            "case_id": case["case_id"],
            "category": case["category"],
            "group_id": case.get("group_id"),
            "user_request": case["user_request"],
        },
        "group": group,
        "resolved": resolved_view,
        "members": members,
        "travelers": travelers,
        "preferences": preferences,
        "flights": backend.get("flights") or (rows("flights", origin_city=origin, destination=destination) if destination else []),
        "hotels": backend.get("hotels") or (rows("hotels", destination=destination) if destination else []),
        "tours": backend.get("tours") or (rows("tours", destination=destination) if destination else []),
        "data_source": backend.get("source") or "local_csv_fallback",
    }
    return {"context": context}


def picks_from_specialists(state: CaseState) -> dict[str, Any]:
    """Эксперимент ranked candidates: LLM-специалисты ранжируют варианты, а код только
    проверяет, что выбранный id реально есть в context. Детерминированный best_* — fallback."""
    flight = state.get("flight_analysis") or {}
    hotel = state.get("hotel_analysis") or {}
    tour = state.get("tour_analysis") or {}

    return {
        "flight_id": (
            _first_existing_ranked(state, "flights", "flight_id", _ranked_ids(flight, "flight_id"))
            or _best_flight_from_context(state)
        ),
        "hotel_id": (
            _first_existing_ranked(state, "hotels", "hotel_id", _ranked_ids(hotel, "hotel_id"))
            or (
                tour.get("linked_hotel_id")
                if isinstance(tour.get("linked_hotel_id"), str)
                and tour.get("linked_hotel_id") in _context_ids(state, "hotels", "hotel_id")
                else None
            )
            or _best_hotel_from_context(state)
        ),
        "tour_id": (
            _first_existing_ranked(state, "tours", "tour_id", _ranked_ids(tour, "tour_id"))
            or tour.get("recommended_tour_id")
        ),
    }


def carry_entities(draft: dict[str, Any], state: CaseState) -> dict[str, Any]:
    fixed = b3.carry_entities(draft, state)
    if not isinstance(fixed, dict):
        return fixed
    ents = fixed.get("entities")
    if not isinstance(ents, dict):
        ents = {}
    picks = picks_from_specialists(state)
    ents["flight_id"] = picks.get("flight_id") or ents.get("flight_id")
    ents["hotel_id"] = picks.get("hotel_id") or ents.get("hotel_id")
    ents["tour_id"] = picks.get("tour_id") or ents.get("tour_id")
    fixed["entities"] = ents
    return fixed


def compute_feasibility(state: CaseState) -> dict[str, Any]:
    """Детерминированный калькулятор фактов (инструмент, не решение). Считает стоимость плана
    (без двойного счёта пакетного тура), бюджет (приоритет — бюджет из запроса), укладывается ли
    план в бюджет и структурные нарушения. Решение об исходе принимает агент по этим фактам.
    Работает и без группы: бюджет/ночи берутся из извлечённых из переписки фактов."""
    case = state["case"]
    intent = state.get("intent_analysis") or {}
    resolved = state.get("resolve") or {}
    picks = picks_from_specialists(state)
    flight = _lookup_context(state, "flights", "flight_id", picks.get("flight_id"))
    hotel = _lookup_context(state, "hotels", "hotel_id", picks.get("hotel_id"))
    tour = _lookup_context(state, "tours", "tour_id", picks.get("tour_id"))
    context = state.get("context") or {}
    group = context.get("group") or get_group(case.get("group_id"))
    n = nights(group) if group else resolved.get("nights")

    violations: list[str] = []
    constraint_text = _constraint_text(state)
    if group:
        for label, row in (("перелёт", flight), ("отель", hotel), ("тур", tour)):
            if row and row.get("destination") and row["destination"] != group["destination"]:
                violations.append(f"{label} не совпадает с направлением группы {group['destination']}")

    # Стоимость без двойного счёта: пакетный тур уже включает перелёт/отель.
    total = 0
    if tour:
        total += safe_int(tour.get("total_price_rub")) or 0
        if flight and not _truthy_flag(tour.get("includes_flight")):
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
    if group:
        budget = eff if eff else safe_int(group.get("budget_rub"))
    else:
        budget = eff if eff else resolved.get("budget_rub")
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
            "baggage_included": _truthy_flag(flight.get("baggage_included")),
            "arrival_time": flight.get("arrival_time"),
        }
        if ("только прям" in constraint_text or "прямой рейс" in constraint_text) and not chosen["flight"]["direct"]:
            violations.append("требуется прямой рейс, но выбран перелёт с пересадкой")
        if ("багаж" in constraint_text or "baggage" in constraint_text) and not chosen["flight"]["baggage_included"]:
            violations.append("требуется багаж, но в выбранный тариф багаж не включён")
    if hotel:
        chosen["hotel"] = {
            "stars": safe_int(hotel.get("stars")),
            "breakfast_included": _truthy_flag(hotel.get("breakfast_included")),
            "free_cancellation": _truthy_flag(hotel.get("free_cancellation")),
            "rating": hotel.get("rating"),
        }
        if ("только 5" in constraint_text or "5*" in constraint_text or "5 зв" in constraint_text) and (chosen["hotel"]["stars"] or 0) < 5:
            violations.append("требуется отель 5*, но выбран отель ниже 5*")
        if ("завтрак" in constraint_text or "breakfast" in constraint_text) and not chosen["hotel"]["breakfast_included"]:
            violations.append("требуется завтрак, но выбран отель без завтрака")
        if ("бесплатн" in constraint_text and "отмен" in constraint_text) and not chosen["hotel"]["free_cancellation"]:
            violations.append("требуется бесплатная отмена, но у выбранного отеля её нет")
    if tour:
        chosen["tour"] = {
            "includes_flight": _truthy_flag(tour.get("includes_flight")),
            "includes_transfer": _truthy_flag(tour.get("includes_transfer")),
        }

    return {
        "total_cost_rub": total or None,
        "effective_budget_rub": budget,
        "budget_source": "из запроса" if eff else ("группы" if group else "из переписки"),
        "within_budget": within_budget,
        "structural_violations": violations,
        "chosen": chosen,
        "nights": n,
    }


def feasibility_node(state: CaseState) -> dict[str, Any]:
    return {"feasibility": compute_feasibility(state)}


def _plan_block(state: CaseState) -> dict[str, Any]:
    """Структурированный план для agent-service: направление/вылет/даты/итог для карты и persist.
    Работает и без группы (берёт из context.resolved + feasibility)."""
    context = state.get("context") or {}
    resolved = context.get("resolved") or {}
    feasibility = state.get("feasibility") or {}
    return {
        "origin_city": resolved.get("origin_city"),
        "origin_code": resolved.get("origin_code"),
        "destination": resolved.get("destination_label"),
        "destination_code": resolved.get("destination_code"),
        "start_date": resolved.get("start_date"),
        "end_date": resolved.get("end_date"),
        "estimated_total_rub": feasibility.get("total_cost_rub"),
    }


# ── Supervisor / finalizer / critic ─────────────────────────────────────────────────────────────

def supervisor_node(state: CaseState) -> dict[str, Any]:
    case = state["case"]
    package = {
        "intent_analysis": state["intent_analysis"],
        "flight_analysis": state["flight_analysis"],
        "hotel_analysis": state["hotel_analysis"],
        "tour_analysis": state["tour_analysis"],
        "policy_analysis": state["policy_analysis"],
        "feasibility": state["feasibility"],
        "resolved": (state.get("context") or {}).get("resolved", {}),
        "feedback": state["feedback"],
    }
    prompt = (
        "Ты Supervisor травел-агента. Прими решение из анализа специалистов и ФАКТОВ выполнимости. "
        "Не придумывай id — бери только из анализов специалистов.\n"
        + OUTCOME_GUIDE
        + "\nОпирайся на факты feasibility (бюджет и атрибуты посчитаны детерминированно, им можно доверять):\n"
        "- recommendation требует ОБОИХ: within_budget!=false И выбранный план (chosen) удовлетворяет ВСЕ "
        "жёсткие требования пользователя из запроса. Сам сверь запрос с chosen: 'только прямой' → "
        "chosen.flight.direct=true; 'только 5*'/'не ниже 4*' → chosen.hotel.stars; нужен багаж/завтрак/"
        "отмена → соответствующие поля. structural_violations должны быть пусты.\n"
        "- если within_budget=false ИЛИ какое-то жёсткое требование не выполнено/конфликтует ИЛИ есть "
        "structural_violations: ПО УМОЛЧАНИЮ clarification — предложи компромисс или уточни приоритет. "
        "rejection ставь ТОЛЬКО если пользователь в запросе явно запретил любой компромисс.\n"
        "- escalation — только если policy_analysis.requires_escalation=true с конкретным обоснованием.\n"
        "Если outcome_type=clarification, заполни поле options списком из 2-4 коротких вариантов ответа "
        "(например 'Увеличить бюджет', 'Сменить даты', 'Другое направление'), когда это уместно; иначе [].\n"
        "Если outcome_type=recommendation, в answer КРАТКО опиши план словами: направление, даты, что входит "
        "(перелёт/отель/тур) и итоговую стоимость — и предложи подтвердить.\n"
        "Верни только minified JSON: "
        "{\"outcome_type\":\"recommendation|clarification|escalation|rejection|info\","
        "\"entities\":{\"flight_id\":null,\"hotel_id\":null,\"tour_id\":null},\"options\":[],\"answer\":\"...\"}\n"
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
        + "\nИспользуй факты feasibility как основу для outcome_type. Сохрани options из черновика, если они есть. "
        "Верни только minified JSON: "
        "{\"outcome_type\":\"recommendation|clarification|escalation|rejection|info\","
        "\"entities\":{\"flight_id\":null,\"hotel_id\":null,\"tour_id\":null},\"options\":[],\"answer\":\"...\"}\n"
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
    # Сохрани варианты ответа и приложи структурный план (направление/даты/итог) для agent-service.
    if not fixed.get("options") and isinstance(draft, dict) and draft.get("options"):
        fixed["options"] = draft["options"]
    fixed.setdefault("options", [])
    fixed["plan"] = _plan_block(state)
    return {"raw": dump_draft(fixed), "draft": fixed}


def critic_node(state: CaseState) -> dict[str, Any]:
    """Критик заземляется на ФАКТЫ выполнимости (а не на детерминированный код): если факты и исход
    рассогласованы — отправляет на переделку."""
    case, draft = state["case"], state["draft"]
    prompt = (
        "Ты CriticAgent. Проверь, согласован ли итог с фактами выполнимости и запросом. "
        "Верни только minified JSON: {\"ok\":true|false,\"feedback\":\"...\"}.\n"
        "ok=false, если: within_budget!=false, structural_violations пусты И выбранный план (chosen) "
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
    graph.add_node("resolve", resolve_node)
    graph.add_node("direct_info", direct_info_node)
    graph.add_node("policy_info", policy_info_node)
    graph.add_node("clarify", clarify_node)
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
    graph.add_edge(START, "resolve")
    graph.add_conditional_edges(
        "resolve",
        route_resolve,
        {
            "direct_info": "direct_info",
            "policy_info": "policy_info",
            "clarify": "clarify",
            "load_context": "load_context",
        },
    )
    graph.add_edge("direct_info", END)
    graph.add_edge("policy_info", END)
    graph.add_edge("clarify", END)
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
            "resolve": {},
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


def run_case_with_retries(app, case: dict[str, Any], attempts: int = 3) -> str:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return run_case(app, case)
        except Exception as exc:  # transient LLM/API timeout на одном кейсе не должен портить весь eval
            last_exc = exc
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)
    raise last_exc or RuntimeError("case failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    qa = load_qa()
    b1.build_agent()        # инициализирует policy RAG vectorstore
    b3.LLM = b3.build_llm()  # переиспользуемые узлы B3 берут LLM из его модуля
    app = build_graph()

    if args.case_id:
        case = next(item for item in qa if item["case_id"] == args.case_id)
        print(run_case_with_retries(app, case))
        return

    if args.all:
        for case in qa:
            try:
                prediction = run_case_with_retries(app, case)
            except Exception as exc:  # один сбойный кейс (напр. сетевой/квота) не должен ронять весь прогон
                prediction = json.dumps(
                    {"outcome_type": "clarification", "entities": {}, "answer": f"ERROR: {exc}"},
                    ensure_ascii=False,
                )
            print(json.dumps({"case_id": case["case_id"], "prediction": prediction}, ensure_ascii=False), flush=True)
        return

    print("Укажи --case-id Q-001 или --all")


if __name__ == "__main__":
    main()
