from __future__ import annotations

from fastapi import Header, HTTPException

from .config import get_settings


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"error": {"code": "unauthorized", "message": "Missing or invalid service token."}},
    )


async def require_service_token(authorization: str | None = Header(default=None)) -> None:
    """Contract A auth: Authorization: Bearer <AGENT_SERVICE_TOKEN>."""
    expected = get_settings().agent_service_token
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()
    if authorization.removeprefix("Bearer ").strip() != expected:
        raise _unauthorized()


async def require_correlation_id(x_correlation_id: str | None = Header(default=None)) -> str:
    if not x_correlation_id:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "validation_error", "message": "X-Correlation-ID is required."}},
        )
    return x_correlation_id
