import httpx
import pytest

from travel_backend.clients.agent_service import AgentServiceClient
from travel_backend.config import Settings
from travel_backend.errors import APIError


def settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        agent_service_url="http://agent.test",
        agent_service_token="token",
    )


async def test_agent_client_create_and_stream_with_mock_transport():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/runs":
            assert request.headers["X-Correlation-ID"] == "corr"
            return httpx.Response(
                202,
                json={
                    "agent_run_id": "agent-1",
                    "thread_id": "thread-1",
                    "status": "started",
                    "stream_url": "/v1/runs/agent-1/stream",
                },
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=(
                "id: 1\n"
                "event: message\n"
                'data: {"agent_run_id":"agent-1","message":{"id":"m1",'
                '"role":"assistant","content":"Готово"}}\n\n'
                "id: 2\n"
                "event: run_status\n"
                'data: {"agent_run_id":"agent-1","status":"completed",'
                '"outcome":"recommendation"}\n\n'
            ),
        )

    service = AgentServiceClient(settings())
    await service.client.aclose()
    service.client = httpx.AsyncClient(
        base_url="http://agent.test",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer token"},
    )
    created = await service.create_run({"mode": "qa"}, "corr")
    assert created.agent_run_id == "agent-1"
    events = [event async for event in service.stream(created.stream_url, "corr")]
    assert [event.event for event in events] == ["message", "run_status"]
    assert events[0].data["message"]["content"] == "Готово"
    await service.close()


async def test_agent_client_maps_transport_timeout_to_controlled_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    service = AgentServiceClient(settings())
    await service.client.aclose()
    service.client = httpx.AsyncClient(
        base_url="http://agent.test",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(APIError) as captured:
        await service.create_run({"mode": "qa"}, "corr")
    assert captured.value.status_code == 504
    assert captured.value.code == "timeout"
    await service.close()

