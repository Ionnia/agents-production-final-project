from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agent" / "baselines"))

from evaluate_predictions import parse_prediction  # noqa: E402


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path, key: str) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return {row[key]: row for row in csv.DictReader(f)}


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def truthy(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes", "да"}


def nights(group: dict[str, str] | None) -> int | None:
    if not group:
        return None
    try:
        return max((date.fromisoformat(group["end_date"]) - date.fromisoformat(group["start_date"])).days, 1)
    except (KeyError, ValueError):
        return None


def effective_budget(case: dict[str, Any], group: dict[str, str] | None) -> tuple[int | None, str]:
    request = case.get("user_request", "").lower()
    group_budget = as_int(group.get("budget_rub")) if group else None
    delta = re.search(r"(?:сократился|уменьшился|снизился)\D{0,20}(\d[\d\s]*)", request)
    if delta and group_budget:
        value = as_int(delta.group(1).replace(" ", ""))
        if value:
            return group_budget - value, f"бюджет группы {group_budget} минус {value} из запроса"
    explicit = re.search(
        r"(?:\bбюджет(?:\s*(?:до|в|=|:))?|\bуложись\s+в|\bв\s+пределах|\bдо)\s+(\d[\d\s]*)",
        request,
    )
    if explicit:
        value = as_int(explicit.group(1).replace(" ", ""))
        if value:
            return value, f"явно из запроса: {value}"
    return group_budget, f"бюджет группы: {group_budget}" if group_budget else "бюджет не задан"


def row_title(row: dict[str, str] | None, kind: str) -> str:
    if not row:
        return f"{kind}: не выбран"
    if kind == "flight":
        return (
            f"{row['flight_id']}: {row['origin_city']}→{row['destination']}, "
            f"{row['price_rub']} ₽, stops={row['stops']}, baggage={row['baggage_included']}, "
            f"{row['departure_time']}–{row['arrival_time']}"
        )
    if kind == "hotel":
        return (
            f"{row['hotel_id']}: {row['destination']}, {row['stars']}*, "
            f"{row['price_per_night_rub']} ₽/ночь, breakfast={row['breakfast_included']}, "
            f"cancel={row['free_cancellation']}, rating={row['rating']}"
        )
    return (
        f"{row['tour_id']}: {row['destination']}, {row['total_price_rub']} ₽, "
        f"includes_flight={row['includes_flight']}, transfer={row['includes_transfer']}, hotel={row['hotel_id']}"
    )


def cost_breakdown(
    flight: dict[str, str] | None,
    hotel: dict[str, str] | None,
    tour: dict[str, str] | None,
    n: int | None,
) -> tuple[int | None, list[str]]:
    total = 0
    lines: list[str] = []
    if tour:
        price = as_int(tour.get("total_price_rub")) or 0
        total += price
        lines.append(f"тур {tour['tour_id']}: {price} ₽")
        if flight and not truthy(tour.get("includes_flight")):
            price = as_int(flight.get("price_rub")) or 0
            total += price
            lines.append(f"рейс {flight['flight_id']}: {price} ₽")
        if hotel and tour.get("hotel_id") != hotel.get("hotel_id"):
            price = (as_int(hotel.get("price_per_night_rub")) or 0) * (n or 1)
            total += price
            lines.append(f"отель {hotel['hotel_id']}: {hotel['price_per_night_rub']} × {n or 1} = {price} ₽")
    else:
        if flight:
            price = as_int(flight.get("price_rub")) or 0
            total += price
            lines.append(f"рейс {flight['flight_id']}: {price} ₽")
        if hotel and n:
            price = (as_int(hotel.get("price_per_night_rub")) or 0) * n
            total += price
            lines.append(f"отель {hotel['hotel_id']}: {hotel['price_per_night_rub']} × {n} = {price} ₽")
    return (total if lines else None), lines


def entity_line(expected: dict[str, Any], predicted: dict[str, Any]) -> str:
    keys = ["flight_id", "hotel_id", "tour_id"]
    parts = []
    for key in keys:
        exp = expected.get(key)
        pred = predicted.get(key)
        if exp or pred:
            mark = "OK" if exp == pred else ("EXTRA" if pred and not exp else "MISS")
            parts.append(f"{key}: expected={exp}, predicted={pred} ({mark})")
    return "; ".join(parts) if parts else "нет ожидаемых сущностей"


def constraint_violations(
    case: dict[str, Any],
    group: dict[str, str] | None,
    flight: dict[str, str] | None,
    hotel: dict[str, str] | None,
) -> list[str]:
    text = " ".join(
        part.lower()
        for part in [case.get("user_request", ""), (group or {}).get("group_comment", "")]
        if part
    )
    violations = []
    if flight:
        if ("только прям" in text or "прямой рейс" in text) and as_int(flight.get("stops")) != 0:
            violations.append(f"нужен прямой рейс, но {flight['flight_id']} имеет stops={flight['stops']}")
        if "багаж" in text and not truthy(flight.get("baggage_included")):
            violations.append(f"нужен багаж, но в {flight['flight_id']} baggage_included={flight['baggage_included']}")
        hour = as_int((flight.get("arrival_time") or "")[:2])
        if ("без ноч" in text or "ночн" in text) and hour is not None and (hour >= 23 or hour < 6):
            violations.append(f"нельзя ночной прилёт, но {flight['flight_id']} прилетает в {flight['arrival_time']}")
    if hotel:
        if ("только 5" in text or "5*" in text or "только 5*" in text) and (as_int(hotel.get("stars")) or 0) < 5:
            violations.append(f"нужен отель 5*, но {hotel['hotel_id']} имеет {hotel['stars']}*")
        if "завтрак" in text and not truthy(hotel.get("breakfast_included")):
            violations.append(f"нужен завтрак, но в {hotel['hotel_id']} breakfast_included={hotel['breakfast_included']}")
        if "бесплат" in text and "отмен" in text and not truthy(hotel.get("free_cancellation")):
            violations.append(f"нужна бесплатная отмена, но в {hotel['hotel_id']} free_cancellation={hotel['free_cancellation']}")
    return violations


def conclusion(
    case: dict[str, Any],
    pred: dict[str, Any],
    outcome_ok: bool,
    entity_ok: bool,
    total: int | None,
    budget: int | None,
    violations: list[str],
) -> str:
    if outcome_ok and entity_ok:
        return "агент совпал с разметкой: outcome и ожидаемые сущности корректны"
    if violations:
        return "выбранный план нарушает жёсткие ограничения: " + "; ".join(violations)
    if budget and total and total > budget:
        gap = total - budget
        return f"выбранный/ожидаемый план дороже эффективного бюджета на {gap} ₽; поэтому clarification/rejection может быть продуктово оправдан"
    if not outcome_ok and entity_ok:
        return "сущности найдены верно, ошибка только в типе исхода"
    if outcome_ok and not entity_ok:
        return "тип исхода верный, но есть несовпадение по ID сущностей"
    return "есть расхождение и по типу исхода, и/или по выбранным сущностям"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions")
    parser.add_argument("--output", "-o", default="agent/PREDICTION_EXPLANATIONS.md")
    args = parser.parse_args()

    qa = {row["case_id"]: row for row in read_jsonl(ROOT / "data" / "qa" / "qa.jsonl")}
    groups = read_csv(ROOT / "data" / "travelers" / "travel_groups.csv", "group_id")
    flights = read_csv(ROOT / "data" / "travelers" / "flights.csv", "flight_id")
    hotels = read_csv(ROOT / "data" / "travelers" / "hotels.csv", "hotel_id")
    tours = read_csv(ROOT / "data" / "travelers" / "tours.csv", "tour_id")

    blocks = ["# Agent Prediction Explanations", ""]
    summary = {"cases": 0, "outcome_ok": 0, "matched_entities": 0, "expected_entities": 0}

    for outer in read_jsonl(Path(args.predictions)):
        case = qa[outer["case_id"]]
        pred = parse_prediction(str(outer.get("prediction", "")))
        entities = pred.get("entities") or {}
        plan = pred.get("plan") if isinstance(pred.get("plan"), dict) else {}
        expected_entities = case.get("expected_entities") or {}
        group = groups.get(case.get("group_id") or "")
        flight = flights.get(entities.get("flight_id") or "")
        hotel = hotels.get(entities.get("hotel_id") or "")
        tour = tours.get(entities.get("tour_id") or "")
        n = nights(group)
        budget, budget_source = effective_budget(case, group)
        total, cost_lines = cost_breakdown(flight, hotel, tour, n)
        violations = constraint_violations(case, group, flight, hotel)
        outcome_ok = pred.get("outcome_type") == case.get("expected_outcome_type")
        entity_ok = all(entities.get(key) == value for key, value in expected_entities.items())

        summary["cases"] += 1
        summary["outcome_ok"] += int(outcome_ok)
        summary["matched_entities"] += sum(entities.get(key) == value for key, value in expected_entities.items())
        summary["expected_entities"] += len(expected_entities)

        blocks.extend(
            [
                f"## {case['case_id']} — {case['category']}",
                "",
                f"- Запрос: {case['user_request']}",
                f"- Expected outcome: `{case['expected_outcome_type']}`; agent outcome: `{pred.get('outcome_type')}`; status: {'OK' if outcome_ok else 'MISS'}",
                f"- Entities: {entity_line(expected_entities, entities)}",
                f"- Group: `{case.get('group_id')}`; budget: {budget if budget is not None else 'unknown'} ₽ ({budget_source}); nights: {n if n is not None else 'unknown'}",
                f"- Flight: {row_title(flight, 'flight')}",
                f"- Hotel: {row_title(hotel, 'hotel')}",
                f"- Tour: {row_title(tour, 'tour')}",
                f"- Cost: {total if total is not None else 'not calculated'} ₽",
                f"- Agent plan estimated_total_rub: {plan.get('estimated_total_rub') if plan else 'not provided'}",
            ]
        )
        if cost_lines:
            blocks.append(f"- Breakdown: {'; '.join(cost_lines)}")
        if budget is not None and total is not None:
            diff = total - budget
            blocks.append(f"- Budget diff: {diff:+} ₽")
        if plan and plan.get("estimated_total_rub") is not None and total is not None:
            plan_total = as_int(plan.get("estimated_total_rub"))
            if plan_total != total:
                blocks.append(f"- Plan/entity cost mismatch: plan={plan_total} ₽, entities={total} ₽")
        blocks.append(f"- Constraint violations: {'; '.join(violations) if violations else 'нет'}")
        blocks.extend(
            [
                f"- Agent answer: {pred.get('answer', '')}",
                f"- Conclusion: {conclusion(case, pred, outcome_ok, entity_ok, total, budget, violations)}",
                "",
            ]
        )

    blocks.insert(
        2,
        "Cases: "
        f"{summary['cases']}; outcome OK: {summary['outcome_ok']}; "
        f"entities OK: {summary['matched_entities']}/{summary['expected_entities']}",
    )
    blocks.insert(3, "")

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(blocks), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
