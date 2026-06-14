import asyncio

from conftest import register_user
from sqlalchemy import func, select

from travel_backend.database import SessionFactory
from travel_backend.models import RefreshToken, User


async def test_password_and_refresh_tokens_are_hashed(client, unique_email):
    registered, _ = await register_user(client, unique_email)
    raw_refresh = registered["tokens"]["refresh_token"]
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        token = await db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
        assert user.password_hash != "password123"
        assert user.password_hash.startswith("$argon2")
        assert token.token_hash != raw_refresh
        assert len(token.token_hash) == 64


async def test_login_logout_me_and_unauthenticated_access(client, unique_email):
    _, headers = await register_user(client, unique_email)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "password123"},
    )
    assert login.status_code == 200
    refresh = login.json()["refresh_token"]

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == unique_email

    denied = await client.get("/api/v1/sessions")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "unauthorized"
    assert denied.json()["error"]["message"] == "Требуется авторизация."

    logout = await client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": refresh},
    )
    assert logout.status_code == 204
    rejected = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert rejected.status_code == 401


async def test_refresh_rotation_is_atomic_under_concurrency(client, unique_email):
    registered, _ = await register_user(client, unique_email)
    refresh_token = registered["tokens"]["refresh_token"]

    responses = await asyncio.gather(
        client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}),
        client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}),
    )

    assert sorted(response.status_code for response in responses) == [200, 401]
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        total = await db.scalar(
            select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        active = await db.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    assert total == 2
    assert active == 1
