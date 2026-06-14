from datetime import UTC

from fastapi import APIRouter, Response
from sqlalchemy import select

from ..config import get_settings
from ..errors import APIError
from ..models import RefreshToken, User, utcnow
from ..schemas import LoginRequest, RefreshRequest, RegisterRequest
from ..security import (
    CurrentUser,
    Database,
    create_access_token,
    hash_password,
    hash_token,
    issue_refresh_token,
    verify_password,
)
from ..services.serializers import iso

router = APIRouter(prefix="/auth", tags=["Auth"])


def user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "created_at": iso(user.created_at),
    }


async def token_bundle(db: Database, user: User) -> dict:
    settings = get_settings()
    access, expires_in = create_access_token(user.id, settings)
    refresh, _ = await issue_refresh_token(db, user.id, settings)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: Database) -> dict:
    email = body.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise APIError(409, "conflict", details={"field": "email"})
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()
    tokens = await token_bundle(db, user)
    await db.commit()
    return {"user": user_dict(user), "tokens": tokens}


@router.post("/login")
async def login(body: LoginRequest, db: Database) -> dict:
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise APIError(401, "unauthorized")
    tokens = await token_bundle(db, user)
    await db.commit()
    return {**tokens, "user": user_dict(user)}


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: Database) -> dict:
    settings = get_settings()
    entity = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token))
    )
    now = utcnow()
    if entity is None:
        raise APIError(401, "unauthorized")
    expires_at = entity.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if entity.revoked_at is not None or expires_at <= now:
        raise APIError(401, "token_expired" if expires_at <= now else "unauthorized")
    user = await db.get(User, entity.user_id)
    if user is None:
        raise APIError(401, "unauthorized")
    new_refresh, replacement = await issue_refresh_token(db, user.id, settings)
    entity.revoked_at = now
    entity.replaced_by_hash = replacement.token_hash
    access, expires_in = create_access_token(user.id, settings)
    await db.commit()
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest, user: CurrentUser, db: Database) -> Response:
    entity = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(body.refresh_token),
            RefreshToken.user_id == user.id,
        )
    )
    if entity is None:
        raise APIError(401, "unauthorized")
    entity.revoked_at = utcnow()
    await db.commit()
    return Response(status_code=204)


@router.get("/me")
async def me(user: CurrentUser) -> dict:
    return user_dict(user)
