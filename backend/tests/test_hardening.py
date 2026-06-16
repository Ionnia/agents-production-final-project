import logging
from pathlib import Path
from uuid import uuid4

import pytest
from conftest import create_group, register_user, tool_headers
from sqlalchemy import func, select

from travel_backend.config import Settings
from travel_backend.database import SessionFactory
from travel_backend.errors import APIError
from travel_backend.models import (
    ChatSession,
    GroupMember,
    Plan,
    Run,
    RunEvent,
    TravelGroup,
    User,
)
from travel_backend.services.runs import fail_run, process_agent_event

PROTECTED_ROUTES = [
    ("POST", "/api/v1/auth/logout", {"refresh_token": "x" * 20}),
    ("GET", "/api/v1/auth/me", None),
    ("POST", "/api/v1/chat", {"message": "test"}),
    ("POST", "/api/v1/chat/missing/stream-ticket", None),
    ("POST", "/api/v1/chat/missing/cancel", None),
    ("GET", "/api/v1/sessions", None),
    ("GET", "/api/v1/sessions/missing", None),
    ("GET", "/api/v1/groups", None),
    ("POST", "/api/v1/groups", {}),
    ("GET", "/api/v1/groups/missing", None),
    ("GET", "/api/v1/groups/missing/members", None),
    ("GET", "/api/v1/groups/missing/preferences", None),
    ("GET", "/api/v1/groups/missing/plans", None),
    ("GET", "/api/v1/plans/missing", None),
    ("POST", "/api/v1/plans/missing/accept", None),
    ("POST", "/api/v1/plans/missing/reject", None),
    ("POST", "/api/v1/plans/missing/modify", {"note": "test"}),
    ("GET", "/api/v1/plans/missing/map", None),
    ("GET", "/api/v1/plans/missing/calendar", None),
]


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED_ROUTES)
async def test_every_protected_api_route_requires_access_jwt(client, method, path, body):
    response = await client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_every_internal_route_rejects_user_jwt(client, unique_email):
    _, headers = await register_user(client, unique_email)
    headers["X-Correlation-ID"] = "user-jwt-is-not-a-service-token"
    calls = [
        ("GET", "/internal/groups/G-0001/context", None),
        (
            "POST",
            "/internal/groups/G-0001/preferences",
            {"preferences": [{"type": "meal", "value": "breakfast"}]},
        ),
        ("POST", "/internal/flights/search", {"origin": "Moscow", "destination": "IST"}),
        ("POST", "/internal/hotels/search", {"destination": "IST"}),
        ("POST", "/internal/tours/search", {"destination": "IST"}),
        (
            "POST",
            "/internal/plans/validate",
            {"group_id": "G-0001", "plan": {"flight_id": "FL-102"}},
        ),
    ]
    for method, path, body in calls:
        response = await client.request(method, path, headers=headers, json=body)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


async def test_internal_api_calls_do_not_modify_business_tables(client):
    async with SessionFactory() as db:
        before = {
            "groups": await db.scalar(select(func.count()).select_from(TravelGroup)),
            "members": await db.scalar(select(func.count()).select_from(GroupMember)),
            "plans": await db.scalar(select(func.count()).select_from(Plan)),
        }
    calls = [
        ("GET", "/internal/groups/G-0001/context", None),
        ("POST", "/internal/flights/search", {"origin": "Moscow", "destination": "IST"}),
        ("POST", "/internal/hotels/search", {"destination": "IST"}),
        ("POST", "/internal/tours/search", {"destination": "IST"}),
        (
            "POST",
            "/internal/plans/validate",
            {"group_id": "G-0001", "plan": {"flight_id": "FL-102"}},
        ),
    ]
    for method, path, body in calls:
        response = await client.request(method, path, headers=tool_headers(), json=body)
        assert response.status_code == 200
    async with SessionFactory() as db:
        after = {
            "groups": await db.scalar(select(func.count()).select_from(TravelGroup)),
            "members": await db.scalar(select(func.count()).select_from(GroupMember)),
            "plans": await db.scalar(select(func.count()).select_from(Plan)),
        }
    assert after == before


async def test_http_localization_defaults_and_falls_back_to_russian(client):
    default = await client.get("/api/v1/auth/me")
    unsupported = await client.get(
        "/api/v1/auth/me",
        headers={"Accept-Language": "de-DE"},
    )
    english = await client.get(
        "/api/v1/auth/me",
        headers={"Accept-Language": "en-US"},
    )
    assert default.json()["error"]["code"] == "unauthorized"
    assert unsupported.json()["error"]["code"] == "unauthorized"
    assert default.json()["error"]["message"] == unsupported.json()["error"]["message"]
    assert any("а" <= char.lower() <= "я" for char in default.json()["error"]["message"])
    assert english.json()["error"]["message"] == "Authentication is required."


async def test_request_logging_excludes_credentials_and_query_tokens(
    client,
    unique_email,
    caplog,
):
    registered, headers = await register_user(client, unique_email)
    password = "never-log-this-password"
    refresh = registered["tokens"]["refresh_token"]
    access = registered["tokens"]["access_token"]
    query_ticket = "never-log-this-stream-ticket"
    caplog.set_level(logging.INFO, logger="travel_backend")

    await client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": password},
    )
    await client.get(
        f"/api/v1/chat/missing/stream?ticket={query_ticket}",
        headers=headers,
    )
    logs = caplog.text
    for secret in (password, refresh, access, query_ticket, "test-tool-token"):
        assert secret not in logs


async def test_env_example_uses_placeholders_for_secrets():
    values = {}
    env_path = Path(__file__).resolve().parents[1] / ".env.example"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    assert values["JWT_SECRET"].startswith("replace-with-")
    assert values["BACKEND_TOOL_TOKEN"].startswith("replace-with-")
    assert values["AGENT_SERVICE_TOKEN"].startswith("replace-with-")
    assert "test-" not in env_path.read_text(encoding="utf-8")


def test_settings_can_be_built_without_a_real_env_file():
    settings = Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret="local-test-secret-with-sufficient-length",
        access_token_ttl_minutes=15,
        refresh_token_ttl_days=30,
        backend_tool_token="local-tool-placeholder",
        agent_service_url="http://agent.test",
        agent_service_token="local-agent-placeholder",
        default_locale="ru-RU",
        supported_locales=["ru-RU", "en-US"],
        cors_origins=["http://localhost:5173"],
        log_level="INFO",
    )
    assert settings.default_locale == "ru-RU"
    wildcard_values = settings.model_dump()
    wildcard_values["cors_origins"] = ["*"]
    with pytest.raises(ValueError):
        Settings(_env_file=None, **wildcard_values)


async def test_agent_events_are_validated_and_sensitive_messages_are_normalized(
    client,
    unique_email,
):
    await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Normalization")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            agent_run_id="agent-expected",
            correlation_id=str(uuid4()),
            mode="qa",
            status="running",
            input_payload={"message": "test", "locale": "ru-RU"},
        )
        db.add(run)
        await db.flush()

        await process_agent_event(
            db,
            run,
            "constraints_conflict",
            {
                "agent_run_id": "agent-expected",
                "message": "UNTRUSTED ENGLISH MESSAGE",
                "suggested_relaxations": [],
            },
        )
        await process_agent_event(
            db,
            run,
            "escalation",
            {
                "agent_run_id": "agent-expected",
                "reason": "policy",
                "message": "UNTRUSTED ESCALATION",
            },
        )
        before = await db.scalar(
            select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run.id)
        )
        await process_agent_event(
            db,
            run,
            "observability",
            {"agent_run_id": "agent-expected", "kind": "node_started"},
        )
        after = await db.scalar(
            select(func.count()).select_from(RunEvent).where(RunEvent.run_id == run.id)
        )
        assert after == before

        messages = (
            await db.scalars(
                select(RunEvent)
                .where(RunEvent.run_id == run.id, RunEvent.event_name == "message")
                .order_by(RunEvent.sequence)
            )
        ).all()
        contents = [item.payload["message"]["content"] for item in messages]
        assert all("UNTRUSTED" not in content for content in contents)
        assert all(any("а" <= char.lower() <= "я" for char in content) for content in contents)

        with pytest.raises(APIError):
            await process_agent_event(
                db,
                run,
                "message_delta",
                {
                    "agent_run_id": "different-agent",
                    "message_id": "m1",
                    "delta": "bad",
                },
            )
        with pytest.raises(APIError) as oversized_message_id:
            await process_agent_event(
                db,
                run,
                "message_delta",
                {
                    "agent_run_id": "agent-expected",
                    "message_id": "m" * 201,
                    "delta": "bad",
                },
            )
        assert oversized_message_id.value.details["source"] == "agent_message_delta"

        with pytest.raises(APIError) as route_preview:
            await process_agent_event(
                db,
                run,
                "route_preview",
                {
                    "agent_run_id": "agent-expected",
                    "points": [],
                },
            )
        assert route_preview.value.details["source"] == "agent_event"

        await process_agent_event(
            db,
            run,
            "clarifying_question",
            {
                "agent_run_id": "agent-expected",
                "question": {
                    "id": "question-1",
                    "text": "Choose one",
                    "options": [
                        {
                            "id": "option-1",
                            "label": "First",
                            "private_score": 0.99,
                        }
                    ],
                    "allow_freeform": False,
                    "internal_prompt": "private",
                },
            },
        )
        question_event = await db.scalar(
            select(RunEvent)
            .where(
                RunEvent.run_id == run.id,
                RunEvent.event_name == "clarifying_question",
            )
            .order_by(RunEvent.sequence.desc())
        )
        assert question_event.payload["question"] == {
            "id": "question-1",
            "text": "Choose one",
            "options": [{"id": "option-1", "label": "First"}],
            "allow_freeform": False,
        }

        await process_agent_event(
            db,
            run,
            "error",
            {
                "agent_run_id": "agent-expected",
                "error": {
                    "code": "agent-invented-secret-code",
                    "message": "UNTRUSTED ERROR TEXT",
                },
            },
        )
        error_event = await db.scalar(
            select(RunEvent)
            .where(RunEvent.run_id == run.id, RunEvent.event_name == "error")
            .order_by(RunEvent.sequence.desc())
        )
        assert error_event.payload["error"]["code"] == "internal"
        assert "UNTRUSTED" not in error_event.payload["error"]["message"]


async def test_agent_plan_destination_mismatch_is_rejected(client, unique_email):
    await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(
            user_id=user.id,
            group_id="G-0001",
            summary="Destination mismatch",
        )
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            group_id="G-0001",
            agent_run_id="agent-destination",
            correlation_id=str(uuid4()),
            mode="qa",
            status="running",
            input_payload={"message": "test", "locale": "ru-RU"},
        )
        db.add(run)
        await db.flush()
        with pytest.raises(APIError) as captured:
            await process_agent_event(
                db,
                run,
                "plan",
                {
                    "agent_run_id": "agent-destination",
                    "plan": {
                        "destination": "DXB",
                        "selections": {"flight_id": "FL-102", "hotel_id": "HT-045"},
                        "map_points": [],
                    },
                },
            )
        assert captured.value.code == "validation_error"
        assert captured.value.details["hard_violations"][0]["code"] == ("plan_destination_mismatch")


async def test_plan_status_gates_accept_modify_and_map_editing(client, unique_email):
    _, headers = await register_user(client, unique_email)
    group = await create_group(client, headers)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, group_id=group["id"], summary="Building")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            group_id=group["id"],
            correlation_id=str(uuid4()),
            mode="qa",
            status="running",
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.flush()
        plan = Plan(
            user_id=user.id,
            session_id=session.id,
            group_id=group["id"],
            run_id=run.id,
            status="building",
        )
        db.add(plan)
        await db.commit()
        plan_id = plan.id
    assert (
        await client.post(f"/api/v1/plans/{plan_id}/accept", headers=headers)
    ).status_code == 409
    assert (
        await client.post(
            f"/api/v1/plans/{plan_id}/modify",
            headers=headers,
            json={"note": "change"},
        )
    ).status_code == 409
    map_response = await client.get(f"/api/v1/plans/{plan_id}/map", headers=headers)
    assert map_response.status_code == 200
    assert map_response.json()["editable"] is False


async def test_building_plan_failure_uses_run_locale(client, unique_email):
    await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="English plan failure")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id=str(uuid4()),
            mode="qa",
            status="running",
            input_payload={"message": "test", "locale": "en-US"},
        )
        db.add(run)
        await db.flush()
        plan = Plan(
            user_id=user.id,
            session_id=session.id,
            run_id=run.id,
            status="building",
        )
        db.add(plan)
        await db.flush()
        run.active_plan_id = plan.id

        await fail_run(db, run, APIError(422, "validation_error"))
        await db.commit()
        events = (
            await db.scalars(
                select(RunEvent)
                .where(
                    RunEvent.run_id == run.id,
                    RunEvent.event_name.in_(("plan_status", "error")),
                )
                .order_by(RunEvent.sequence)
            )
        ).all()

    assert plan.status == "error"
    assert events[0].payload["error"] == "Check the submitted data."
    assert events[1].payload["error"]["message"] == "Check the submitted data."
