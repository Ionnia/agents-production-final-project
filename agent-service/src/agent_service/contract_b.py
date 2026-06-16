from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class ContractBError(Exception):
    """Raised when the backend Internal Tool API (Contract B) is unreachable or returns an error."""


class ContractBClient:
    """Client for the backend's Contract B (`/internal/*`, Variant B business-data access)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.backend_base_url.rstrip("/") + "/internal/"
        self._token = settings.backend_tool_token
        self._timeout = httpx.Timeout(
            connect=settings.backend_connect_timeout_seconds,
            read=settings.backend_read_timeout_seconds,
            write=10.0,
            pool=5.0,
        )

    def _headers(self, correlation_id: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "X-Correlation-ID": correlation_id}

    async def _request(self, method: str, path: str, correlation_id: str, json: Any = None) -> dict[str, Any]:
        url = self._base_url + path.lstrip("/")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(method, url, json=json, headers=self._headers(correlation_id))
        except httpx.HTTPError as exc:
            raise ContractBError(f"Contract B request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ContractBError(f"Contract B {path} returned {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise ContractBError("Contract B returned non-JSON body") from exc
        if not isinstance(data, dict):
            raise ContractBError("Contract B returned a non-object body")
        return data

    async def group_context(self, group_id: str, correlation_id: str) -> dict[str, Any]:
        return await self._request("GET", f"groups/{group_id}/context", correlation_id)

    async def search_flights(self, body: dict[str, Any], correlation_id: str) -> list[dict[str, Any]]:
        data = await self._request("POST", "flights/search", correlation_id, json=body)
        return list(data.get("items", []))

    async def search_hotels(self, body: dict[str, Any], correlation_id: str) -> list[dict[str, Any]]:
        data = await self._request("POST", "hotels/search", correlation_id, json=body)
        return list(data.get("items", []))

    async def search_tours(self, body: dict[str, Any], correlation_id: str) -> list[dict[str, Any]]:
        data = await self._request("POST", "tours/search", correlation_id, json=body)
        return list(data.get("items", []))

    async def validate_plan(self, body: dict[str, Any], correlation_id: str) -> dict[str, Any]:
        return await self._request("POST", "plans/validate", correlation_id, json=body)

    async def save_preferences(
        self, group_id: str, body: dict[str, Any], correlation_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"groups/{group_id}/preferences",
            correlation_id,
            json=body,
        )
