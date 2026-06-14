from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Annotated
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .database import get_db
from .errors import APIError
from .models import RefreshToken, User, utcnow

password_hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, settings: Settings) -> tuple[str, int]:
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": user_id,
        "type": "access",
        "jti": str(uuid4()),
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), int(
        (expires - now).total_seconds()
    )


async def issue_refresh_token(
    db: AsyncSession, user_id: str, settings: Settings
) -> tuple[str, RefreshToken]:
    raw = token_urlsafe(48)
    entity = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(raw),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
    )
    db.add(entity)
    await db.flush()
    return raw, entity


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None:
        raise APIError(401, "unauthorized")
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError as exc:
        raise APIError(401, "token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise APIError(401, "unauthorized") from exc
    if payload.get("type") != "access" or not payload.get("sub"):
        raise APIError(401, "unauthorized")
    user = await db.get(User, payload["sub"])
    if user is None:
        raise APIError(401, "unauthorized")
    return user


async def require_tool_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    x_correlation_id: Annotated[str | None, Header(alias="X-Correlation-ID")] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> str:
    if credentials is None or credentials.credentials != settings.backend_tool_token:
        raise APIError(401, "unauthorized")
    if not x_correlation_id:
        raise APIError(422, "validation_error", details={"header": "X-Correlation-ID"})
    request.state.correlation_id = x_correlation_id
    return x_correlation_id


CurrentUser = Annotated[User, Depends(get_current_user)]
Database = Annotated[AsyncSession, Depends(get_db)]

