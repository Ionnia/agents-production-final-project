"""Deterministic destination/origin resolution used by the Final agent.

These guard the behaviour the user reported: the agent must not loop on a destination it
cannot plan — it offers the catalogue instead — and must disambiguate a country with
several cities. No LLM is involved; this is pure string resolution.
"""
from __future__ import annotations

import travel_catalog as cat

# Mirrors data/travelers offers: six destinations, two origins.
TABLES = {
    "flights": [{"destination": d} for d in ["IST", "DXB", "BKK", "AYT", "BCN", "HKT"]],
    "hotels": [{"destination": d} for d in ["IST", "DXB", "BKK", "AYT", "BCN", "HKT"]],
    "tours": [{"destination": d} for d in ["DXB", "AYT", "HKT"]],
}
AVAILABLE = cat.available_codes(TABLES)


def test_available_codes_are_the_dataset_destinations():
    assert set(AVAILABLE) == {"IST", "DXB", "BKK", "AYT", "BCN", "HKT"}


def test_unavailable_destination_returns_nothing():
    # Greece / Italy are not in the catalogue → resolution is empty → agent offers options.
    assert cat.match_destinations("Помоги спланировать путешествие по Греции", AVAILABLE) == []
    assert cat.match_destinations("поездка в Италию", AVAILABLE) == []


def test_country_with_several_cities_is_ambiguous():
    assert set(cat.match_destinations("хочу в Турцию", AVAILABLE)) == {"IST", "AYT"}
    assert set(cat.match_destinations("Таиланд, пляж", AVAILABLE)) == {"BKK", "HKT"}


def test_city_match_is_specific_and_wins_over_country():
    assert cat.match_destinations("давайте Стамбул", AVAILABLE) == ["IST"]
    assert cat.match_destinations("Дубай", AVAILABLE) == ["DXB"]
    assert cat.match_destinations("Барселона", AVAILABLE) == ["BCN"]


def test_origin_resolution():
    assert cat.match_origin("Город вылета Москва!") == "Moscow"
    assert cat.match_origin("вылет из Санкт-Петербурга") == "St Petersburg"
    assert cat.match_origin("просто хочу на море") is None


def test_labels_and_options():
    assert cat.label_for_code("IST") == "Турция (Стамбул)"
    assert cat.city_for_code("IST") == "Стамбул"
    labels = [o["label"] for o in cat.destination_options(AVAILABLE)]
    assert "Турция (Стамбул)" in labels and "ОАЭ (Дубай)" in labels
    assert cat.origin_label("Moscow") == "Москва"
