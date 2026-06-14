from conftest import register_user


async def test_auth_refresh_rotation_and_russian_errors(client, unique_email):
    registered, headers = await register_user(client, unique_email)
    assert registered["user"]["email"] == unique_email

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={"name": "Другой", "email": unique_email, "password": "password123"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"
    assert any("а" <= char.lower() <= "я" for char in duplicate.json()["error"]["message"])

    refresh_token = registered["tokens"]["refresh_token"]
    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != refresh_token

    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "unauthorized"

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200


async def test_public_groups_are_private_and_seed_groups_are_hidden(client, unique_email):
    _, headers = await register_user(client, unique_email)
    created = await client.post(
        "/api/v1/groups",
        headers=headers,
        json={
            "name": "Семейная поездка",
            "budget_rub": 180000,
            "origin_city": "Moscow",
            "destination": "IST",
            "start_date": "2026-07-10",
            "end_date": "2026-07-15",
            "members": [
                {
                    "full_name": "Иван Тестов",
                    "age": 35,
                    "preferences": [
                        {"type": "meal", "value": "breakfast", "comment": "Нужен завтрак"}
                    ],
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    group = created.json()
    assert group["members"][0]["preferences"][0]["type"] == "meal"

    listed = await client.get("/api/v1/groups", headers=headers)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert group["id"] in ids
    assert "G-0001" not in ids

    _, other_headers = await register_user(client, unique_email.replace("user", "other"))
    hidden = await client.get(f"/api/v1/groups/{group['id']}", headers=other_headers)
    assert hidden.status_code == 404
