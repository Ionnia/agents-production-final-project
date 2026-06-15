"""Exercises the real Final-graph resolution nodes (no LLM): resolve → route → clarify.

This guards the wiring the user's bug exposed — an unavailable destination must route to a
clarifying question that offers the catalogue, and a country with several cities must ask
which city, all deterministically. The graph must also compile. Skipped when the optional
LLM stack (langgraph/langchain) is not installed in this environment.
"""
from __future__ import annotations

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langchain_gigachat")

import final_agent as fa  # noqa: E402
import travel_catalog as cat  # noqa: E402

AVAILABLE = cat.available_codes(fa.b1.TABLES)


def _state(user_text: str, group_id=None) -> dict:
    return {
        "case": {
            "case_id": "t",
            "category": "planning",
            "group_id": group_id,
            "user_request": user_text,
            "user_text_only": user_text,
        },
        "resolve": {},
        "rounds": 0,
    }


def _resolve(user_text: str, group_id=None) -> dict:
    state = _state(user_text, group_id)
    state.update(fa.resolve_node(state))
    return state


def test_unavailable_destination_routes_to_clarify_with_catalogue_options():
    state = _resolve("Помоги спланировать путешествие по Греции")
    assert fa.route_resolve(state) == "clarify"
    draft = fa.clarify_node(state)["draft"]
    assert draft["outcome_type"] == "clarification"
    expected = {o["label"] for o in cat.destination_options(AVAILABLE)}
    assert set(draft["options"]) == expected


def test_ambiguous_country_routes_to_clarify_with_city_options():
    state = _resolve("Хочу в Турцию, вылет из Москвы")
    assert fa.route_resolve(state) == "clarify"
    draft = fa.clarify_node(state)["draft"]
    assert set(draft["options"]) == {"Турция (Стамбул)", "Турция (Анталья)"}


def test_destination_known_but_origin_missing_asks_origin():
    state = _resolve("Хочу в Стамбул")
    assert fa.route_resolve(state) == "clarify"
    draft = fa.clarify_node(state)["draft"]
    assert set(draft["options"]) == {"Москва", "Санкт-Петербург"}


def test_resolved_destination_and_origin_proceeds_to_planning():
    state = _resolve("Стамбул, вылет из Москвы, 5–15 июля")
    assert state["resolve"]["dest_code"] == "IST"
    assert state["resolve"]["origin"] == "Moscow"
    assert fa.route_resolve(state) == "load_context"


def test_group_id_always_proceeds_to_planning():
    state = _resolve("любой запрос", group_id="G-0001")
    assert fa.route_resolve(state) == "load_context"


def test_group_path_uses_city_labels_not_airport_codes():
    # G-0001 is Moscow → IST in the seed; the plan must surface human names, not codes.
    state = {
        "case": {"case_id": "t", "category": "planning", "group_id": "G-0001",
                 "user_request": "подбери поездку", "user_text_only": "подбери поездку"},
        "resolve": {"group": True},
    }
    resolved = fa.load_context_node(state)["context"]["resolved"]
    assert resolved["destination_label"] == "Стамбул"
    assert resolved["destination_code"] == "IST"
    assert resolved["origin_city"] == "Москва"


def test_graph_compiles():
    assert fa.build_graph() is not None
