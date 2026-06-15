"""Destination catalog and deterministic conversation helpers for the Final agent.

This module is intentionally dependency-free (no langchain / chromadb / csv side
effects on import) so the resolution logic can be unit-tested in isolation and reused
by the agent-service planner. The agent graph imports it; the offer dataset
(`llm_tool_rag_baseline.TABLES`) is passed in at call time via ``available_codes``.

The dataset only contains a fixed set of destinations (airport codes) reachable from
Moscow / St Petersburg. When a user asks for somewhere that is not in the catalogue
(e.g. «Греция», «Италия») the agent must NOT loop on generic questions — it offers the
destinations it can actually plan as selectable clarifying-question options.
"""
from __future__ import annotations

from typing import Any

# code → human label (short city) + city-specific aliases + country aliases.
# City aliases are unique per code; country aliases may map to several codes (e.g. two
# Turkish cities), which the agent surfaces as an ambiguity to disambiguate with options.
DESTINATION_CATALOG: dict[str, dict[str, Any]] = {
    "IST": {
        "label": "Турция (Стамбул)",
        "city": "Стамбул",
        "city_aliases": ["стамбул", "istanbul", "ist"],
        "country_aliases": ["турция", "турцию", "турции", "turkey"],
    },
    "AYT": {
        "label": "Турция (Анталья)",
        "city": "Анталья",
        "city_aliases": ["анталья", "анталия", "анталью", "antalya", "ayt"],
        "country_aliases": ["турция", "турцию", "турции", "turkey"],
    },
    "DXB": {
        "label": "ОАЭ (Дубай)",
        "city": "Дубай",
        "city_aliases": ["дубай", "дубая", "dubai", "dxb"],
        "country_aliases": ["оаэ", "эмираты", "эмираты", "uae", "emirates"],
    },
    "BKK": {
        "label": "Таиланд (Бангкок)",
        "city": "Бангкок",
        "city_aliases": ["бангкок", "bangkok", "bkk"],
        "country_aliases": ["таиланд", "тайланд", "таиланде", "thailand"],
    },
    "HKT": {
        "label": "Таиланд (Пхукет)",
        "city": "Пхукет",
        "city_aliases": ["пхукет", "пхукете", "phuket", "hkt"],
        "country_aliases": ["таиланд", "тайланд", "таиланде", "thailand"],
    },
    "BCN": {
        "label": "Испания (Барселона)",
        "city": "Барселона",
        "city_aliases": ["барселона", "барселону", "барселоне", "barcelona", "bcn"],
        "country_aliases": ["испания", "испанию", "испании", "spain"],
    },
}

# Origin city -> exact dataset value (flights.origin_city) + aliases.
ORIGIN_CATALOG: dict[str, dict[str, Any]] = {
    "Moscow": {
        "label": "Москва",
        "aliases": [
            "москва", "москвы", "москве", "московск", "moscow", "msk",
            "свo", "svo", "dme", "vko", "шереметьево", "домодедово", "внуково",
        ],
    },
    "St Petersburg": {
        "label": "Санкт-Петербург",
        "aliases": [
            "санкт-петербург", "санкт петербург", "петербург", "спб", "питер",
            "saint petersburg", "st petersburg", "led", "пулково",
        ],
    },
}


def available_codes(tables: dict[str, list[dict[str, str]]]) -> list[str]:
    """Destination codes that actually have offers, in catalogue order."""
    present: set[str] = set()
    for table in ("flights", "hotels", "tours"):
        for row in tables.get(table, []):
            code = row.get("destination")
            if code:
                present.add(code)
    return [code for code in DESTINATION_CATALOG if code in present]


def label_for_code(code: str | None) -> str | None:
    if not code:
        return None
    entry = DESTINATION_CATALOG.get(code)
    return entry["label"] if entry else code


def city_for_code(code: str | None) -> str | None:
    if not code:
        return None
    entry = DESTINATION_CATALOG.get(code)
    return entry["city"] if entry else code


def destination_options(available: list[str]) -> list[dict[str, str]]:
    """[{code,label}] for the destinations the agent can plan — used as clarifying options."""
    return [{"code": code, "label": DESTINATION_CATALOG[code]["label"]} for code in available]


def match_destinations(text: str, available: list[str]) -> list[str]:
    """Resolve free text to destination codes, most-specific first.

    Returns: [] (none found / unavailable), [one] (resolved), or [several] (ambiguous —
    e.g. a country with several cities in the catalogue → disambiguate with options).
    City matches win over country matches so «Стамбул» → [IST] even though «Турция»
    alone → [IST, AYT].
    """
    low = (text or "").lower()
    avail = set(available)
    city_hits = [
        code
        for code in DESTINATION_CATALOG
        if code in avail
        and any(alias in low for alias in DESTINATION_CATALOG[code]["city_aliases"])
    ]
    if city_hits:
        return _dedupe(city_hits)
    country_hits = [
        code
        for code in DESTINATION_CATALOG
        if code in avail
        and any(alias in low for alias in DESTINATION_CATALOG[code]["country_aliases"])
    ]
    return _dedupe(country_hits)


def match_origin(text: str) -> str | None:
    low = (text or "").lower()
    for origin, entry in ORIGIN_CATALOG.items():
        if any(alias in low for alias in entry["aliases"]):
            return origin
    return None


def origin_label(origin: str | None) -> str | None:
    if not origin:
        return None
    entry = ORIGIN_CATALOG.get(origin)
    return entry["label"] if entry else origin


def origin_options() -> list[dict[str, str]]:
    return [{"city": city, "label": entry["label"]} for city, entry in ORIGIN_CATALOG.items()]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
