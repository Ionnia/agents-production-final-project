import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from ..errors import APIError
from ..schemas import AgentEvent

MAX_AGENT_SSE_EVENT_BYTES = 1_100_000


@dataclass
class CreatedRun:
    agent_run_id: str
    thread_id: str
    stream_url: str


class AgentClient:
    def __init__(self, settings: Settings) -> None:
        timeout = httpx.Timeout(
            connect=settings.agent_connect_timeout_seconds,
            read=settings.agent_read_timeout_seconds,
            write=10.0,
            pool=5.0,
        )
        self.base_url = httpx.URL(settings.agent_service_url.rstrip("/") + "/")
        self.service_token = settings.agent_service_token
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def close(self) -> None:
        await self.client.aclose()

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.service_token}"}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except (ValueError, TypeError) as exc:
            raise APIError(502, "agent_unavailable") from exc
        if not isinstance(data, dict):
            raise APIError(502, "agent_unavailable")
        return data

    def _stream_path(self, stream_url: str, agent_run_id: str) -> str:
        try:
            parsed = httpx.URL(stream_url)
        except (TypeError, ValueError) as exc:
            raise APIError(502, "agent_unavailable") from exc
        expected_path = f"/v1/runs/{agent_run_id}/stream"
        if parsed.is_absolute_url:
            if (
                parsed.scheme != self.base_url.scheme
                or parsed.host != self.base_url.host
                or parsed.port != self.base_url.port
            ):
                raise APIError(502, "agent_unavailable")
        if parsed.path != expected_path or parsed.query:
            raise APIError(502, "agent_unavailable")
        return expected_path

    async def create_run(self, payload: dict, correlation_id: str) -> CreatedRun:
        try:
            response = await self.client.post(
                "/v1/runs",
                json=payload,
                headers=self._headers(correlation_id),
            )
        except httpx.TimeoutException as exc:
            raise APIError(504, "timeout") from exc
        except httpx.HTTPError as exc:
            raise APIError(502, "agent_unavailable") from exc
        if response.status_code >= 500:
            raise APIError(502, "agent_unavailable")
        if response.status_code >= 400:
            raise APIError(502, "agent_unavailable", details={"status": response.status_code})
        data = self._json_object(response)
        agent_run_id = data.get("agent_run_id")
        thread_id = data.get("thread_id")
        status = data.get("status")
        stream_url = data.get("stream_url")
        if (
            not isinstance(agent_run_id, str)
            or not agent_run_id
            or not isinstance(thread_id, str)
            or not thread_id
            or status != "started"
            or not isinstance(stream_url, str)
        ):
            raise APIError(502, "agent_unavailable")
        return CreatedRun(agent_run_id, thread_id, self._stream_path(stream_url, agent_run_id))

    async def stream(
        self, stream_url: str, correlation_id: str, last_event_id: str | None = None
    ) -> AsyncIterator[AgentEvent]:
        headers = self._headers(correlation_id)
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        try:
            async with self.client.stream("GET", stream_url, headers=headers) as response:
                response.raise_for_status()
                event_name: str | None = None
                event_id: str | None = None
                data_lines: list[str] = []
                frame_size = 0
                async for line in response.aiter_lines():
                    if not line:
                        if event_name and data_lines:
                            yield AgentEvent(
                                event=event_name,
                                id=event_id,
                                data=json.loads("\n".join(data_lines)),
                            )
                        event_name = None
                        event_id = None
                        data_lines = []
                        frame_size = 0
                        continue
                    frame_size += len(line.encode("utf-8")) + 1
                    if frame_size > MAX_AGENT_SSE_EVENT_BYTES:
                        raise APIError(502, "agent_unavailable")
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("id:"):
                        event_id = line[3:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())
                if event_name and data_lines:
                    yield AgentEvent(
                        event=event_name,
                        id=event_id,
                        data=json.loads("\n".join(data_lines)),
                    )
        except httpx.TimeoutException as exc:
            raise APIError(504, "timeout") from exc
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            raise APIError(502, "agent_unavailable") from exc

    async def get_run(self, agent_run_id: str, correlation_id: str) -> dict:
        try:
            response = await self.client.get(
                f"/v1/runs/{agent_run_id}",
                headers=self._headers(correlation_id),
            )
        except httpx.TimeoutException as exc:
            raise APIError(504, "timeout") from exc
        except httpx.HTTPError as exc:
            raise APIError(502, "agent_unavailable") from exc
        if response.status_code >= 500:
            raise APIError(502, "agent_unavailable")
        if response.status_code >= 400:
            raise APIError(
                502,
                "agent_unavailable",
                details={"status": response.status_code},
            )
        data = self._json_object(response)
        required = {"agent_run_id", "thread_id", "status", "started_at"}
        if not required <= data.keys() or data["agent_run_id"] != agent_run_id:
            raise APIError(502, "agent_unavailable")
        return data

    async def cancel(self, agent_run_id: str, correlation_id: str) -> None:
        try:
            response = await self.client.post(
                f"/v1/runs/{agent_run_id}/cancel",
                headers=self._headers(correlation_id),
            )
            if response.status_code not in (202, 409):
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(504, "timeout") from exc
        except httpx.HTTPError as exc:
            raise APIError(502, "agent_unavailable") from exc

    async def get_thread_state(self, thread_id: str, correlation_id: str) -> dict:
        return await self._get_json(
            f"/v1/threads/{thread_id}/state",
            correlation_id,
            required={"thread_id"},
            expected_id=("thread_id", thread_id),
        )

    async def health(self) -> dict:
        return await self._get_json("/v1/health", required={"status"}, authenticated=False)

    async def info(self) -> dict:
        return await self._get_json(
            "/v1/info",
            required={"service", "version"},
        )

    async def _get_json(
        self,
        path: str,
        correlation_id: str | None = None,
        *,
        required: set[str],
        expected_id: tuple[str, str] | None = None,
        authenticated: bool = True,
    ) -> dict:
        headers = self._headers(correlation_id) if authenticated else {}
        try:
            response = await self.client.get(path, headers=headers)
        except httpx.TimeoutException as exc:
            raise APIError(504, "timeout") from exc
        except httpx.HTTPError as exc:
            raise APIError(502, "agent_unavailable") from exc
        if response.status_code >= 400:
            raise APIError(502, "agent_unavailable", details={"status": response.status_code})
        data = self._json_object(response)
        if not required <= data.keys():
            raise APIError(502, "agent_unavailable")
        if expected_id and data.get(expected_id[0]) != expected_id[1]:
            raise APIError(502, "agent_unavailable")
        return data


AgentServiceClient = AgentClient
