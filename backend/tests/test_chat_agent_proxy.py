import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from conftest import create_group, register_user
from sqlalchemy import func, select

from travel_backend.clients.agent_service import CreatedRun
from travel_backend.database import SessionFactory, engine
from travel_backend.errors import APIError
from travel_backend.models import ChatSession, Message, Plan, Run, RunEvent, User
from travel_backend.schemas import AgentEvent
from travel_backend.services.runs import (
    build_agent_payload,
    execute_run,
    process_persisted_agent_event,
)


class SuccessfulAgentClient:
    create_payload: dict | None = None
    correlation_id: str | None = None

    def __init__(self, settings):
        self.settings = settings
        self.agent_run_id: str | None = None
        self.thread_id: str | None = None
        self.agent_message_id: str | None = None

    async def create_run(self, payload: dict, correlation_id: str) -> CreatedRun:
        type(self).create_payload = payload
        type(self).correlation_id = correlation_id
        self.agent_run_id = f"agent-{payload['external_run_id']}"
        self.thread_id = f"thread-{payload['session_id']}"
        self.agent_message_id = f"message-{payload['external_run_id']}"
        return CreatedRun(
            self.agent_run_id,
            self.thread_id,
            f"/v1/runs/{self.agent_run_id}/stream",
        )

    async def stream(
        self,
        stream_url: str,
        correlation_id: str,
        last_event_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        assert self.agent_run_id
        assert self.agent_message_id
        yield AgentEvent(
            event="message",
            data={
                "agent_run_id": self.agent_run_id,
                "message": {
                    "id": self.agent_message_id,
                    "role": "assistant",
                    "content": "Начинаю планирование.",
                },
            },
        )
        yield AgentEvent(
            event="plan",
            data={
                "agent_run_id": self.agent_run_id,
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
                "agent_run_id": self.agent_run_id,
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
        assert self.agent_run_id
        yield AgentEvent(
            event="plan",
            data={
                "agent_run_id": self.agent_run_id,
                "plan": {
                    "destination": "IST",
                    "selections": {"flight_id": "unknown"},
                    "map_points": [],
                },
            },
        )


class ErrorThenStatusAgentClient(SuccessfulAgentClient):
    async def stream(
        self,
        stream_url: str,
        correlation_id: str,
        last_event_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        assert self.agent_run_id
        yield AgentEvent(
            event="error",
            data={
                "agent_run_id": self.agent_run_id,
                "error": {"code": "agent_failed", "message": "private upstream error"},
            },
        )
        yield AgentEvent(
            event="run_status",
            data={"agent_run_id": self.agent_run_id, "status": "error"},
        )


class ClarifyingModifyAgentClient(SuccessfulAgentClient):
    async def stream(
        self,
        stream_url: str,
        correlation_id: str,
        last_event_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        assert self.agent_run_id
        yield AgentEvent(
            event="clarifying_question",
            data={
                "agent_run_id": self.agent_run_id,
                "question": {
                    "id": "q-modify",
                    "text": "Что именно изменить в маршруте?",
                    "options": [],
                    "allow_freeform": True,
                },
            },
        )
        yield AgentEvent(
            event="run_status",
            data={
                "agent_run_id": self.agent_run_id,
                "status": "completed",
                "outcome": "clarification",
            },
        )


class TimeoutAgentClient(SuccessfulAgentClient):
    async def create_run(self, payload: dict, correlation_id: str) -> CreatedRun:
        raise APIError(504, "timeout")


class DeltaStreamingAgentClient(SuccessfulAgentClient):
    async def stream(
        self,
        stream_url: str,
        correlation_id: str,
        last_event_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        assert self.agent_run_id
        assert self.agent_message_id
        for delta in ("Hello ", "world"):
            yield AgentEvent(
                event="message_delta",
                data={
                    "agent_run_id": self.agent_run_id,
                    "message_id": self.agent_message_id,
                    "delta": delta,
                },
            )
        yield AgentEvent(
            event="message",
            data={
                "agent_run_id": self.agent_run_id,
                "message": {
                    "id": self.agent_message_id,
                    "role": "assistant",
                    "content": "Hello world",
                },
            },
        )
        yield AgentEvent(
            event="run_status",
            data={
                "agent_run_id": self.agent_run_id,
                "status": "completed",
                "outcome": "recommendation",
            },
        )


class CancelAgentClient:
    cancelled: tuple[str, str] | None = None

    def __init__(self, settings):
        self.settings = settings

    async def cancel(self, agent_run_id: str, correlation_id: str) -> None:
        assert engine.pool.checkedout() == 0
        type(self).cancelled = (agent_run_id, correlation_id)

    async def close(self) -> None:
        return None


class FailingCancelAgentClient(CancelAgentClient):
    error_code = "timeout"
    status_code = 504

    async def cancel(self, agent_run_id: str, correlation_id: str) -> None:
        assert engine.pool.checkedout() == 0
        raise APIError(self.status_code, self.error_code, details={"upstream": "private"})


class PausingCancelAgentClient(CancelAgentClient):
    started: asyncio.Event | None = None
    release: asyncio.Event | None = None

    async def cancel(self, agent_run_id: str, correlation_id: str) -> None:
        assert engine.pool.checkedout() == 0
        assert self.started is not None
        assert self.release is not None
        self.started.set()
        await self.release.wait()


class RaceCancelAgentClient(SuccessfulAgentClient):
    """Simulates a cancel landing in the window between create_run and mapping.

    create_run succeeds upstream, then the local run is flipped to a terminal
    state (as a concurrent cancel would do) before save_agent_mapping claims it.
    """

    cancelled: tuple[str, str] | None = None
    race_run_id: str | None = None

    async def create_run(self, payload: dict, correlation_id: str) -> CreatedRun:
        created = await super().create_run(payload, correlation_id)
        async with SessionFactory() as db:
            run = await db.get(Run, type(self).race_run_id)
            run.status = "cancelled"
            await db.commit()
        return created

    async def cancel(self, agent_run_id: str, correlation_id: str) -> None:
        type(self).cancelled = (agent_run_id, correlation_id)


class SessionBoundaryAgentClient(SuccessfulAgentClient):
    async def create_run(self, payload: dict, correlation_id: str) -> CreatedRun:
        assert engine.pool.checkedout() == 0
        return await super().create_run(payload, correlation_id)

    async def stream(
        self,
        stream_url: str,
        correlation_id: str,
        last_event_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        assert engine.pool.checkedout() == 0
        async for event in super().stream(stream_url, correlation_id, last_event_id):
            assert engine.pool.checkedout() == 0
            yield event


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
        assert run.agent_run_id == f"agent-{run_id}"
        assert run.agent_thread_id == f"thread-{run.session_id}"
        assert run.agent_stream_url.endswith("/stream")
        assert run.group_id == group["id"]
        assert run.status == "completed"
        assert run.correlation_id == SuccessfulAgentClient.correlation_id
        plan = await db.scalar(select(Plan).where(Plan.run_id == run.id))
        assert plan.status == "ready"
        assert plan.estimated_total_rub == 130500
        persisted_message = await db.scalar(
            select(Message).where(
                Message.run_id == run.id,
                Message.agent_message_id == f"message-{run.id}",
            )
        )
        assert persisted_message is not None
        assert persisted_message.id != persisted_message.agent_message_id
        events = (
            await db.scalars(
                select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.sequence)
            )
        ).all()

    required_fields = {
        "run_status": {"run_id", "status"},
        "message_delta": {"run_id", "message_id", "delta"},
        "message": {"run_id", "message"},
        "clarifying_question": {"run_id", "question"},
        "plan_status": {"run_id", "plan_id", "status"},
        "map": {"run_id", "plan_id", "points"},
        "error": {"run_id", "error"},
    }
    assert events
    assert {event.event_name for event in events} <= required_fields.keys()
    for event in events:
        assert required_fields[event.event_name] <= event.payload.keys()

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
    session = await client.get(
        f"/api/v1/sessions/{response.json()['session_id']}",
        headers=headers,
    )
    assistant_messages = [
        item for item in session.json()["messages"] if item["role"] == "assistant"
    ]
    assert assistant_messages
    assert all("agent_message_id" not in item for item in assistant_messages)


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
        assert run.error_code == "validation_error"
        count = await db.scalar(select(func.count()).select_from(Plan).where(Plan.run_id == run_id))
        assert count == 0


async def test_agent_error_event_persists_terminal_run_status(client, unique_email, monkeypatch):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        ErrorThenStatusAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    response = await client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Сломай агент"},
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        events = (
            await db.scalars(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence)
            )
        ).all()
    assert run.status == "error"
    assert run.finished_at is not None
    assert [event.event_name for event in events][-2:] == ["error", "run_status"]
    assert events[-1].payload == {"run_id": run_id, "status": "error"}


async def test_streamed_assistant_message_uses_one_backend_owned_id(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        DeltaStreamingAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    response = await client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Stream a reply"},
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    agent_message_id = f"message-{run_id}"

    async with SessionFactory() as db:
        messages = (
            await db.scalars(
                select(Message).where(
                    Message.run_id == run_id,
                    Message.agent_message_id == agent_message_id,
                )
            )
        ).all()
        assert len(messages) == 1
        persisted_message = messages[0]
        assert persisted_message.id != agent_message_id
        assert persisted_message.content == "Hello world"
        events = (
            await db.scalars(
                select(RunEvent)
                .where(
                    RunEvent.run_id == run_id,
                    RunEvent.event_name.in_(("message_delta", "message")),
                )
                .order_by(RunEvent.sequence)
            )
        ).all()

    assert [event.event_name for event in events] == [
        "message_delta",
        "message_delta",
        "message",
    ]
    frontend_ids = [
        events[0].payload["message_id"],
        events[1].payload["message_id"],
        events[2].payload["message"]["id"],
    ]
    assert frontend_ids == [persisted_message.id] * 3

    session = await client.get(
        f"/api/v1/sessions/{response.json()['session_id']}",
        headers=headers,
    )
    assistant_messages = [
        item for item in session.json()["messages"] if item["role"] == "assistant"
    ]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["id"] == persisted_message.id
    assert "agent_message_id" not in assistant_messages[0]


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


async def test_modify_clarification_restores_existing_plan_ready_status(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        ClarifyingModifyAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    plan_id = await create_ready_plan(unique_email)
    response = await client.post(
        f"/api/v1/plans/{plan_id}/modify",
        headers=headers,
        json={"note": "Пока не знаю, что изменить"},
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]

    async with SessionFactory() as db:
        plan = await db.get(Plan, plan_id)
        run = await db.get(Run, run_id)
        events = (
            await db.scalars(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence)
            )
        ).all()
    assert run.status == "completed"
    assert run.outcome == "clarification"
    assert plan.status == "ready"
    assert [event.payload for event in events if event.event_name == "plan_status"][-1] == {
        "run_id": run_id,
        "plan_id": plan_id,
        "status": "ready",
    }


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


async def test_agent_timeout_uses_run_english_locale(
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
        headers={**headers, "Accept-Language": "en-US"},
        json={"message": "Plan a trip"},
    )
    assert response.status_code == 202
    async with SessionFactory() as db:
        run = await db.get(Run, response.json()["run_id"])
        assert run.input_payload["locale"] == "en-US"
        error_event = await db.scalar(
            select(RunEvent).where(
                RunEvent.run_id == run.id,
                RunEvent.event_name == "error",
            )
        )
        assert error_event.payload["error"] == {
            "code": "timeout",
            "message": "The planning service did not respond in time.",
        }


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


async def test_cancel_rejects_concurrent_agent_events_after_local_terminal_status(
    client,
    unique_email,
    monkeypatch,
):
    PausingCancelAgentClient.started = asyncio.Event()
    PausingCancelAgentClient.release = asyncio.Event()
    monkeypatch.setattr(
        "travel_backend.api.chat.AgentServiceClient",
        PausingCancelAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    agent_run_id = f"agent-{uuid4()}"
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Concurrent cancellation")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id=str(uuid4()),
            mode="qa",
            status="running",
            agent_run_id=agent_run_id,
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    cancel_task = asyncio.create_task(client.post(f"/api/v1/chat/{run_id}/cancel", headers=headers))
    await PausingCancelAgentClient.started.wait()
    processed = await process_persisted_agent_event(
        run_id,
        "message",
        {
            "agent_run_id": agent_run_id,
            "message": {
                "id": "message-before-cancel",
                "role": "assistant",
                "content": "Before cancellation",
            },
        },
    )
    assert processed is False
    PausingCancelAgentClient.release.set()
    response = await cancel_task
    assert response.status_code == 202

    processed_after = await process_persisted_agent_event(
        run_id,
        "message",
        {
            "agent_run_id": agent_run_id,
            "message": {
                "id": "message-after-cancel",
                "role": "assistant",
                "content": "After cancellation",
            },
        },
    )
    assert processed_after is False
    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        events = (
            await db.scalars(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence)
            )
        ).all()
    assert run.status == "cancelled"
    assert events[-1].event_name == "run_status"
    assert events[-1].payload["status"] == "cancelled"
    assert all(
        event.payload.get("message", {}).get("content")
        not in {"Before cancellation", "After cancellation"}
        for event in events
    )


@pytest.mark.parametrize(
    ("error_code", "status_code"),
    [("timeout", 504), ("agent_unavailable", 502)],
)
async def test_cancel_normalizes_agent_failures_to_frontend_http_contract(
    client,
    unique_email,
    monkeypatch,
    error_code,
    status_code,
):
    class ControlledFailure(FailingCancelAgentClient):
        pass

    ControlledFailure.error_code = error_code
    ControlledFailure.status_code = status_code
    monkeypatch.setattr(
        "travel_backend.api.chat.AgentServiceClient",
        ControlledFailure,
    )
    _, headers = await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Cancel failure")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id=str(uuid4()),
            mode="qa",
            status="running",
            agent_run_id=f"agent-{uuid4()}",
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.commit()
        run_id = run.id
    response = await client.post(f"/api/v1/chat/{run_id}/cancel", headers=headers)
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal",
            "message": "Произошла внутренняя ошибка сервиса.",
        }
    }


async def test_agent_network_waits_do_not_hold_database_connections(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        SessionBoundaryAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    response = await client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Проверь границы сессии"},
    )
    assert response.status_code == 202
    async with SessionFactory() as db:
        run = await db.get(Run, response.json()["run_id"])
        assert run.status == "completed"


async def test_run_cancelled_before_mapping_cancels_orphaned_agent_run(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        RaceCancelAgentClient,
    )
    RaceCancelAgentClient.cancelled = None
    _, headers = await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Orphan cancellation")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id=str(uuid4()),
            mode="new_trip",
            input_payload={"message": "Подбери поездку"},
            status="started",
        )
        db.add(run)
        await db.commit()
        run_id = run.id
    RaceCancelAgentClient.race_run_id = run_id

    await execute_run(run_id)

    # The upstream agent run that create_run produced must be proactively cancelled
    # rather than left orphaned.
    assert RaceCancelAgentClient.cancelled is not None
    assert RaceCancelAgentClient.cancelled[0] == f"agent-{run_id}"
    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        # The terminal status must be preserved and no mapping stored.
        assert run.status == "cancelled"
        assert run.agent_run_id is None


async def test_agent_payload_uses_per_run_group_snapshot(client, unique_email):
    # A session re-pointed to a different group must not leak its current group
    # into an older run: build_agent_payload must use the run's own snapshot.
    await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(
            user_id=user.id,
            group_id="G-current",
            summary="Re-pointed session",
        )
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            group_id="G-historical",
            correlation_id=str(uuid4()),
            mode="new_trip",
            input_payload={"message": "Подбери поездку", "locale": "ru"},
            status="started",
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    prepared = await build_agent_payload(run_id, "ru")
    assert prepared is not None
    payload, _ = prepared
    assert payload["group_id"] == "G-historical"


async def test_selected_clarification_options_are_forwarded_to_agent_as_labels(
    client,
    unique_email,
    monkeypatch,
):
    monkeypatch.setattr(
        "travel_backend.services.runs.AgentServiceClient",
        SuccessfulAgentClient,
    )
    _, headers = await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Clarification")
        db.add(session)
        await db.flush()
        db.add(
            Message(
                session_id=session.id,
                role="assistant",
                content="Какое условие можно смягчить?",
                question={
                    "id": "q-budget",
                    "text": "Какое условие можно смягчить?",
                    "options": [
                        {"id": "o0", "label": "Увеличить бюджет"},
                        {"id": "o1", "label": "Изменить даты"},
                    ],
                    "allow_freeform": True,
                },
            )
        )
        await db.commit()
        session_id = session.id

    response = await client.post(
        "/api/v1/chat",
        headers=headers,
        json={
            "session_id": session_id,
            "in_reply_to_question_id": "q-budget",
            "selected_option_ids": ["o0"],
        },
    )

    assert response.status_code == 202, response.text
    assert SuccessfulAgentClient.create_payload["answer"] == {
        "in_reply_to_question_id": "q-budget",
        "selected_option_ids": ["o0"],
        "selected_option_labels": ["Увеличить бюджет"],
    }
    async with SessionFactory() as db:
        message = await db.scalar(
            select(Message).where(
                Message.session_id == session_id,
                Message.role == "user",
                Message.answer.is_not(None),
            )
        )
    assert message.content == "Увеличить бюджет"
