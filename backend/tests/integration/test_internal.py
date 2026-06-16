from conftest import register_user, tool_headers


async def test_internal_auth_is_separate_from_user_jwt(client, unique_email):
    _, user_headers = await register_user(client, unique_email)
    user_headers["X-Correlation-ID"] = "test-correlation"
    denied = await client.get("/internal/groups/G-0001/context", headers=user_headers)
    assert denied.status_code == 401

    missing_correlation = await client.get(
        "/internal/groups/G-0001/context",
        headers={"Authorization": "Bearer test-tool-token"},
    )
    assert missing_correlation.status_code == 422

    allowed = await client.get("/internal/groups/G-0001/context", headers=tool_headers())
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["members"][0]["traveler_id"].startswith("T-")


async def test_search_and_plan_validation(client):
    flights = await client.post(
        "/internal/flights/search",
        headers=tool_headers(),
        json={
            "origin": "Moscow",
            "destination": "IST",
            "required_baggage": True,
            "avoid_night_arrival": True,
        },
    )
    assert flights.status_code == 200
    assert [item["flight_id"] for item in flights.json()["items"]] == ["FL-102"]

    valid = await client.post(
        "/internal/plans/validate",
        headers=tool_headers(),
        json={
            "group_id": "G-0001",
            "plan": {"flight_id": "FL-102", "hotel_id": "HT-045"},
            "constraints": {"required_baggage": True},
        },
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["valid"] is True
    assert valid.json()["budget_left_rub"] == 49500

    package = await client.post(
        "/internal/plans/validate",
        headers=tool_headers(),
        json={
            "group_id": "G-0002",
            "plan": {
                "tour_id": "TR-020",
                "flight_id": "FL-205",
                "hotel_id": "HT-101",
            },
        },
    )
    assert package.status_code == 200
    assert package.json()["valid"] is True
    assert package.json()["budget_left_rub"] == 5300


async def test_internal_can_save_agent_memory_preferences(client):
    before = await client.get("/internal/groups/G-0001/context", headers=tool_headers())
    assert before.status_code == 200
    traveler_id = before.json()["members"][0]["traveler_id"]

    payload = {
        "preferences": [
            {
                "traveler_id": traveler_id,
                "type": "departure_time",
                "value": "avoid_early_departure",
                "comment": "Пользователь обычно не любит ранние вылеты",
                "confidence": 0.92,
                "source": "agent_memory",
            }
        ]
    }
    saved = await client.post(
        "/internal/groups/G-0001/preferences",
        headers=tool_headers(),
        json=payload,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved"][0]["type"] == "departure_time"

    duplicate = await client.post(
        "/internal/groups/G-0001/preferences",
        headers=tool_headers(),
        json=payload,
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["saved"] == []
    assert duplicate.json()["skipped"][0]["reason"] == "duplicate"

    after = await client.get("/internal/groups/G-0001/context", headers=tool_headers())
    assert any(
        pref.get("value") == "avoid_early_departure"
        for member in after.json()["members"]
        for pref in member["preferences"]
    )
