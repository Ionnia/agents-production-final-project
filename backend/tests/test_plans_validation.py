from datetime import UTC, datetime
from uuid import uuid4

from conftest import register_user
from sqlalchemy import select

from travel_backend.database import SessionFactory
from travel_backend.models import (
    ChatSession,
    Plan,
    PlanCalendarEvent,
    PlanMapPoint,
    Run,
    User,
)


async def create_ready_plan(email: str) -> str:
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == email))
        session = ChatSession(user_id=user.id, summary="Готовый план")
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
            destination="IST",
        )
        db.add(plan)
        await db.flush()
        db.add_all(
            [
                PlanMapPoint(
                    plan_id=plan.id,
                    name="Стамбул",
                    kind="destination",
                    lat=41.0082,
                    lng=28.9784,
                    order=1,
                ),
                PlanMapPoint(
                    plan_id=plan.id,
                    name="Москва",
                    kind="origin",
                    lat=55.7558,
                    lng=37.6173,
                    order=0,
                ),
                PlanCalendarEvent(
                    plan_id=plan.id,
                    type="hotel",
                    title="Отель",
                    start=datetime(2026, 7, 10, 15, tzinfo=UTC),
                ),
                PlanCalendarEvent(
                    plan_id=plan.id,
                    type="flight",
                    title="Перелёт",
                    start=datetime(2026, 7, 10, 10, 20, tzinfo=UTC),
                ),
            ]
        )
        await db.commit()
        return plan.id


async def test_accept_reject_and_deterministic_map_calendar(client, unique_email):
    _, headers = await register_user(client, unique_email)
    accepted_id = await create_ready_plan(unique_email)

    map_response = await client.get(
        f"/api/v1/plans/{accepted_id}/map",
        headers=headers,
    )
    assert map_response.status_code == 200
    assert [point["kind"] for point in map_response.json()["points"]] == [
        "origin",
        "destination",
    ]
    assert map_response.json()["editable"] is True

    calendar = await client.get(
        f"/api/v1/plans/{accepted_id}/calendar",
        headers=headers,
    )
    assert calendar.status_code == 200
    assert [event["type"] for event in calendar.json()["events"]] == [
        "flight",
        "hotel",
    ]

    accepted = await client.post(
        f"/api/v1/plans/{accepted_id}/accept",
        headers=headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    accepted_map = await client.get(
        f"/api/v1/plans/{accepted_id}/map",
        headers=headers,
    )
    assert accepted_map.json()["editable"] is False
    repeated_accept = await client.post(
        f"/api/v1/plans/{accepted_id}/accept",
        headers=headers,
    )
    assert repeated_accept.status_code == 409
    assert repeated_accept.json()["error"]["code"] == "plan_not_ready"

    rejected_id = await create_ready_plan(unique_email)
    rejected = await client.post(
        f"/api/v1/plans/{rejected_id}/reject",
        headers=headers,
        json={"reason": "Не подходит"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
