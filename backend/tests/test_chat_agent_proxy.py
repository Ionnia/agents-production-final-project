from collections.abc import AsyncIterator
from uuid import uuid4

from conftest import create_group, register_user
from sqlalchemy import func, select

from travel_backend.clients.agent_service import CreatedRun
from travel_backend.database import SessionFactory
from travel_backend.errors import APIError
from travel_backend.models import ChatSession, Plan, Run, RunEvent, User
from travel_backend.schemas import AgentEvent


class SuccessfulAgentClient:
    create_payload: dict | None = None
    correlation_id: str | None = None

    def __init__(self, settings):
        self.settings = settings

    async def create_run(self, payload: dict, correlation_id: str) -> CreatedRun:
        type(self).create_payload = payload
        type(self).correlation_id = correlation_id
        return CreatedRun("agent-run-1", "agent-thread-1", "/v1/runs/agent-run-1/stream")

    async def stream(
        self,
        stream_url: str,
        correlation_id: str,
        last_event_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(
            event="message",
            data={
                "agent_run_id": "agent-run-1",
                "message": {
                    "id": "assistant-1",
                    "role": "assistant",
                    "content": "Начинаю планирование.",
                },
            },
        )
        yield AgentEvent(
            event="plan",
            data={
                "agent_run_id": "agent-run-1",
                "plan": {
                    "destination": "IST",
                    "start_date": "2026-07-10",
                    "end_date": "2026-07-15",
                    "selections": {"flight_id": "FL-102", "hotel_id": "HT-045"},
                    "decision_rationale": "Вариант соответствует ограничениям.",
                    "map_points": [
                        {
                            "name": "Москва",
                            "kind": "origin",
                            "lat": 55.7558,
                            "lng": 37.6173,
                            "order": 0,
                        },
                        {
                            "name": "Стамбул",
                            "kind": "destination",
                            "lat": 41.0082,
                            "lng": 28.9784,
                            "order": 1,
                        },
                    ],
                },
            },
        )
        yield AgentEvent(
            event="run_status",
            data={
                "agent_run_id": "agent-run-1",
                "status": "completed",
                "outcome": "recommendation",
            },
        )

    async def close(self) -> None:
        return None


class InvalidPlanAgentClient(SuccessfulAgentClient):
    async def stream(
        self,
        stream_url: str,
        correlation_id: str,
        last_event_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(
            event="plan",
            data={
                "agent_run_id": "agent-run-1",
                "plan": {
                    "destination": "IST",
                    "selections": {"flight_id": "unknown"},
                    "map_points": [],
                },
            },
        )


class TimeoutAgentClient(SuccessfulAgentClient):
    async def create_run(self, payload: dict, correlation_id: str) -> CreatedRun:
        raise APIError(504, "timeout")


class CancelAgentClient:
    cancelled: tuple[str, str] | None = None

    def __init__(self, settings):
        self.settings = settings

    async def cancel(self, agent_run_id: str, correlation_id: str) -> None:
        type(self).cancelled = (agent_run_id, correlation_id)

    async def close(self) -> None:
        return None


async def create_ready_plan(email: str) -> str:
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == email))
        session = ChatSession(user_id=user.id, summary="План для изменения")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id=str(uuid4()),
            mode="qa",
            status="completed",
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.flush()
        plan = Plan(
            user_id=user.id,
            session_id=session.id,
            run_id=run.id,
            status="ready",
        )
        db.add(plan)
        await db.commit()
        return plan.id


async def test_chat_calls_agent_and_persists_complete_mapping_and_plan(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        SuccessfulAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    group = await create_group(client, headers)
    response = await client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Подбери поездку", "group_id": group["id"]},
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]

    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        assert run.agent_run_id == "agent-run-1"
        assert run.agent_thread_id == "agent-thread-1"
        assert run.agent_stream_url.endswith("/stream")
        assert run.group_id == group["id"]
        assert run.status == "completed"
        assert run.correlation_id == SuccessfulAgentClient.correlation_id
        plan = await db.scalar(select(Plan).where(Plan.run_id == run.id))
        assert plan.status == "ready"
        assert plan.estimated_total_rub == 130500

    assert SuccessfulAgentClient.create_payload["external_run_id"] == run_id
    assert SuccessfulAgentClient.create_payload["group_id"] == group["id"]

    ticket = await client.post(
        f"/api/v1/chat/{run_id}/stream-ticket",
        headers=headers,
    )
    stream = await client.get(f"/api/v1/chat/{run_id}/stream?ticket={ticket.json()['ticket']}")
    assert "event: message" in stream.text
    assert "event: plan_status" in stream.text
    assert "event: map" in stream.text


async def test_invalid_agent_plan_is_not_persisted(client, unique_email, monkeypatch):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        InvalidPlanAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    response = await client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Подбери поездку"},
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        assert run.status == "error"
        count = await db.scalar(select(func.count()).select_from(Plan).where(Plan.run_id == run_id))
        assert count == 0


async def test_modify_starts_agent_run_with_route_edits_and_active_plan(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        SuccessfulAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    plan_id = await create_ready_plan(unique_email)
    response = await client.post(
        f"/api/v1/plans/{plan_id}/modify",
        headers=headers,
        json={
            "add": [
                {
                    "name": "Бурса",
                    "kind": "stop",
                    "lat": 40.195,
                    "lng": 29.06,
                }
            ],
            "note": "Добавить остановку",
        },
    )
    assert response.status_code == 202, response.text
    async with SessionFactory() as db:
        run = await db.get(Run, response.json()["run_id"])
        assert run.mode == "modify"
        assert run.active_plan_id == plan_id
        assert run.input_payload["route_edits"]["note"] == "Добавить остановку"
    assert SuccessfulAgentClient.create_payload["mode"] == "modify"
    assert SuccessfulAgentClient.create_payload["active_plan_id"] == plan_id


async def test_agent_timeout_marks_run_failed_and_emits_safe_russian_error(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        TimeoutAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    response = await client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Подбери поездку"},
    )
    assert response.status_code == 202
    async with SessionFactory() as db:
        run = await db.get(Run, response.json()["run_id"])
        assert run.status == "error"
        error_event = await db.scalar(
            select(RunEvent).where(
                RunEvent.run_id == run.id,
                RunEvent.event_name == "error",
            )
        )
        assert error_event.payload["error"]["code"] == "timeout"
        assert error_event.payload["error"]["message"] == (
            "Сервис планирования не ответил вовремя."
        )


async def test_cancel_calls_agent_service_when_mapping_exists(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.api.chat.AgentServiceClient",
        CancelAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Отмена")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id="cancel-correlation",
            mode="qa",
            status="running",
            agent_run_id="agent-to-cancel",
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.commit()
        run_id = run.id
    response = await client.post(
        f"/api/v1/chat/{run_id}/cancel",
        headers=headers,
    )
    assert response.status_code == 202
    assert CancelAgentClient.cancelled == (
        "agent-to-cancel",
        "cancel-correlation",
    )
