from conftest import tool_headers


async def test_hotel_and_tour_search_filters(client):
    hotels = await client.post(
        "/internal/hotels/search",
        headers=tool_headers(),
        json={
            "destination": "DXB",
            "breakfast_required": True,
            "free_cancellation_preferred": True,
            "min_stars": 4,
            "budget_per_night_rub": 15000,
        },
    )
    assert hotels.status_code == 200
    assert [item["hotel_id"] for item in hotels.json()["items"]] == ["HT-101"]
    assert hotels.json()["items"][0]["breakfast_included"] is True

    tours = await client.post(
        "/internal/tours/search",
        headers=tool_headers(),
        json={
            "destination": "DXB",
            "budget_rub": 220000,
            "includes_flight": True,
            "includes_transfer": True,
        },
    )
    assert tours.status_code == 200
    assert [item["tour_id"] for item in tours.json()["items"]] == ["TR-020"]


async def test_plan_validation_reports_unknown_budget_and_baggage_violations(client):
    unknown = await client.post(
        "/internal/plans/validate",
        headers=tool_headers(),
        json={
            "group_id": "G-0001",
            "plan": {"flight_id": "missing", "hotel_id": "missing"},
        },
    )
    assert unknown.status_code == 200
    assert unknown.json()["valid"] is False
    assert {item["code"] for item in unknown.json()["hard_violations"]} >= {
        "unknown_flight",
        "unknown_hotel",
    }

    invalid = await client.post(
        "/internal/plans/validate",
        headers=tool_headers(),
        json={
            "group_id": "G-0001",
            "plan": {"flight_id": "FL-118", "hotel_id": "HT-045"},
            "constraints": {"required_baggage": True, "budget_rub": 100000},
        },
    )
    assert invalid.status_code == 200
    codes = {item["code"] for item in invalid.json()["hard_violations"]}
    assert "baggage_required" in codes
    assert "budget_exceeded" in codes

    night_arrival = await client.post(
        "/internal/plans/validate",
        headers=tool_headers(),
        json={
            "group_id": "G-0003",
            "plan": {"flight_id": "FL-311", "hotel_id": "HT-205"},
            "constraints": {"avoid_night_flights": True},
        },
    )
    assert night_arrival.status_code == 200
    night_codes = {item["code"] for item in night_arrival.json()["hard_violations"]}
    assert "night_arrival" in night_codes

    destination_mismatch = await client.post(
        "/internal/plans/validate",
        headers=tool_headers(),
        json={
            "group_id": "G-0001",
            "plan": {"flight_id": "FL-205"},
        },
    )
    assert destination_mismatch.status_code == 200
    mismatch_codes = {item["code"] for item in destination_mismatch.json()["hard_violations"]}
    assert "flight_destination_mismatch" in mismatch_codes
