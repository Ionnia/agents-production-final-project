from uuid import uuid4

from conftest import register_user
from sqlalchemy import select

from travel_backend.database import SessionFactory
from travel_backend.models import ChatSession, Plan, Run, User


async def test_user_cannot_read_another_users_session_or_plan(client, unique_email):
    _, owner_headers = await register_user(client, unique_email)
    _, other_headers = await register_user(client, f"other-{unique_email}")
    async with SessionFactory() as db:
        owner = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=owner.id, summary="Приватная поездка")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=owner.id,
            correlation_id=str(uuid4()),
            mode="qa",
            status="completed",
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.flush()
        plan = Plan(
            user_id=owner.id,
            session_id=session.id,
            run_id=run.id,
            status="ready",
        )
        db.add(plan)
        await db.commit()
        session_id = session.id
        plan_id = plan.id

    assert (
        await client.get(f"/api/v1/sessions/{session_id}", headers=owner_headers)
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/sessions/{session_id}", headers=other_headers)
    ).status_code == 404
    assert (await client.get(f"/api/v1/plans/{plan_id}", headers=other_headers)).status_code == 404
    assert (
        await client.post(
            f"/api/v1/plans/{plan_id}/accept",
            headers=other_headers,
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/plans/{plan_id}/modify",
            headers=other_headers,
            json={"note": "Чужое изменение"},
        )
    ).status_code == 404
