from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QA_PATH = ROOT / "data" / "qa" / "qa.jsonl"


def parse_prediction(text: str) -> dict[str, Any]:
    text = text.replace("<|superquote|>", '"')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    outcome_match = re.search(
        r'"?outcome_type"?\s*:\s*"?(recommendation|clarification|escalation|rejection|info)"?',
        text,
        re.I,
    )
    flight_match = re.search(r"\bFL-\d+\b", text)
    hotel_match = re.search(r"\bHT-\d+\b", text)
    tour_match = re.search(r"\bTR-\d+\b", text)
    if not outcome_match and not any([flight_match, hotel_match, tour_match]):
        return {}
    return {
        "outcome_type": outcome_match.group(1).lower() if outcome_match else None,
        "entities": {
            "flight_id": flight_match.group(0) if flight_match else None,
            "hotel_id": hotel_match.group(0) if hotel_match else None,
            "tour_id": tour_match.group(0) if tour_match else None,
        },
        "answer": text,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions")
    args = parser.parse_args()

    qa = {
        item["case_id"]: item
        for item in (
            json.loads(line)
            for line in QA_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }

    rows = []
    for line in Path(args.predictions).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        outer = json.loads(line)
        case_id = outer["case_id"]
        pred = parse_prediction(str(outer.get("prediction", "")))
        expected = qa[case_id]
        pred_entities = pred.get("entities") or {}
        expected_entities = expected.get("expected_entities") or {}
        entity_checks = {
            key: pred_entities.get(key) == value
            for key, value in expected_entities.items()
        }
        rows.append(
            {
                "case_id": case_id,
                "category": expected["category"],
                "expected_outcome": expected["expected_outcome_type"],
                "predicted_outcome": pred.get("outcome_type"),
                "outcome_ok": pred.get("outcome_type") == expected["expected_outcome_type"],
                "entity_checks": entity_checks,
                "parse_ok": bool(pred),
            }
        )

    total = len(rows)
    outcome_ok = sum(row["outcome_ok"] for row in rows)
    entity_total = sum(len(row["entity_checks"]) for row in rows)
    entity_ok = sum(sum(row["entity_checks"].values()) for row in rows)
    parse_ok = sum(row["parse_ok"] for row in rows)

    summary = {
        "cases": total,
        "parse_success_rate": round(parse_ok / total, 3) if total else 0,
        "outcome_accuracy": round(outcome_ok / total, 3) if total else 0,
        "entity_accuracy": round(entity_ok / entity_total, 3) if entity_total else 1,
        "matched_outcomes": outcome_ok,
        "matched_entities": entity_ok,
        "expected_entities": entity_total,
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print()
    for row in rows:
        if not row["outcome_ok"] or not all(row["entity_checks"].values()):
            print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
