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
        if request.url.path == "/v1/runs/agent-1" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "agent_run_id": "agent-1",
                    "thread_id": "thread-1",
                    "status": "running",
                    "started_at": "2026-06-14T10:00:00Z",
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
    snapshot = await service.get_run(created.agent_run_id, "corr")
    assert snapshot["status"] == "running"
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


async def test_agent_client_cancel_sends_correlation_header():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            202,
            json={"agent_run_id": "agent-1", "status": "cancelling"},
        )

    service = AgentServiceClient(settings())
    await service.client.aclose()
    service.client = httpx.AsyncClient(
        base_url="http://agent.test",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer token"},
    )
    await service.cancel("agent-1", "corr")
    assert requests[0].url.path == "/v1/runs/agent-1/cancel"
    assert requests[0].headers["X-Correlation-ID"] == "corr"
    await service.close()


async def test_agent_client_supports_remaining_contract_a_reads_and_eof_frame():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/threads/thread-1/state":
            return httpx.Response(200, json={"thread_id": "thread-1", "state": {}})
        if request.url.path == "/v1/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/info":
            return httpx.Response(200, json={"service": "agent", "version": "1.0"})
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=(
                'id: 1\nevent: run_status\ndata: {"agent_run_id":"agent-1","status":"completed"}'
            ),
        )

    service = AgentServiceClient(settings())
    await service.client.aclose()
    service.client = httpx.AsyncClient(
        base_url="http://agent.test",
        transport=httpx.MockTransport(handler),
    )
    assert (await service.get_thread_state("thread-1", "corr"))["thread_id"] == "thread-1"
    assert (await service.health())["status"] == "ok"
    assert (await service.info())["version"] == "1.0"
    events = [
        event
        async for event in service.stream(
            "/v1/runs/agent-1/stream",
            "corr",
        )
    ]
    assert len(events) == 1
    assert "Authorization" not in requests[1].headers
    assert requests[0].headers["Authorization"] == "Bearer token"
    assert "X-Correlation-ID" not in requests[2].headers
    await service.close()


@pytest.mark.parametrize(
    "response_json",
    [
        {"agent_run_id": "agent-1", "thread_id": "thread-1", "status": "started"},
        {
            "agent_run_id": "agent-1",
            "thread_id": "thread-1",
            "status": "started",
            "stream_url": "https://attacker.example/v1/runs/agent-1/stream",
        },
        {
            "agent_run_id": "agent-1",
            "thread_id": "thread-1",
            "status": "wrong",
            "stream_url": "/v1/runs/agent-1/stream",
        },
    ],
)
async def test_agent_client_rejects_malformed_or_foreign_create_response(response_json):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json=response_json)

    service = AgentServiceClient(settings())
    await service.client.aclose()
    service.client = httpx.AsyncClient(
        base_url="http://agent.test",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(APIError) as captured:
        await service.create_run({"mode": "qa"}, "corr")
    assert captured.value.code == "agent_unavailable"
    await service.close()
