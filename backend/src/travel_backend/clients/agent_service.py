import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from ..config import Settings
from ..errors import APIError
from ..schemas import AgentEvent


@dataclass
class CreatedRun:
    agent_run_id: str
    thread_id: str
    stream_url: str


class AgentServiceClient:
    def __init__(self, settings: Settings) -> None:
        timeout = httpx.Timeout(
            connect=settings.agent_connect_timeout_seconds,
            read=settings.agent_read_timeout_seconds,
            write=10.0,
            pool=5.0,
        )
        self.client = httpx.AsyncClient(
            base_url=settings.agent_service_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {settings.agent_service_token}"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def create_run(self, payload: dict, correlation_id: str) -> CreatedRun:
        try:
            response = await self.client.post(
                "/v1/runs",
                json=payload,
                headers={"X-Correlation-ID": correlation_id},
            )
        except httpx.TimeoutException as exc:
            raise APIError(504, "timeout") from exc
        except httpx.HTTPError as exc:
            raise APIError(502, "agent_unavailable") from exc
        if response.status_code >= 500:
            raise APIError(502, "agent_unavailable")
        if response.status_code >= 400:
            raise APIError(502, "agent_unavailable", details={"status": response.status_code})
        data = response.json()
        return CreatedRun(
            agent_run_id=data["agent_run_id"],
            thread_id=data["thread_id"],
            stream_url=data["stream_url"],
        )

    async def stream(
        self, stream_url: str, correlation_id: str, last_event_id: str | None = None
    ) -> AsyncIterator[AgentEvent]:
        headers = {"X-Correlation-ID": correlation_id}
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        try:
            async with self.client.stream("GET", stream_url, headers=headers) as response:
                response.raise_for_status()
                event_name: str | None = None
                event_id: str | None = None
                data_lines: list[str] = []
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
                        continue
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("id:"):
                        event_id = line[3:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())
        except httpx.TimeoutException as exc:
            raise APIError(504, "timeout") from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise APIError(502, "agent_unavailable") from exc

    async def cancel(self, agent_run_id: str, correlation_id: str) -> None:
        try:
            response = await self.client.post(
                f"/v1/runs/{agent_run_id}/cancel",
                headers={"X-Correlation-ID": correlation_id},
            )
            if response.status_code not in (202, 409):
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise APIError(504, "timeout") from exc
        except httpx.HTTPError as exc:
            raise APIError(502, "agent_unavailable") from exc

