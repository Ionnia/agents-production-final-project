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
    assert (
        await client.post(f"/api/v1/plans/{plan_id}/reject", headers=other_headers)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/plans/{plan_id}/map", headers=other_headers)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/plans/{plan_id}/calendar", headers=other_headers)
    ).status_code == 404


async def test_user_cannot_access_another_users_group_or_run(client, unique_email):
    from conftest import create_group

    _, owner_headers = await register_user(client, unique_email)
    _, other_headers = await register_user(client, f"other-private-{unique_email}")
    group = await create_group(client, owner_headers)
    async with SessionFactory() as db:
        owner = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=owner.id, group_id=group["id"], summary="Private")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=owner.id,
            group_id=group["id"],
            correlation_id=str(uuid4()),
            mode="qa",
            status="completed",
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    for suffix in ("", "/members", "/preferences", "/plans"):
        response = await client.get(
            f"/api/v1/groups/{group['id']}{suffix}",
            headers=other_headers,
        )
        assert response.status_code == 404
    ticket = await client.post(
        f"/api/v1/chat/{run_id}/stream-ticket",
        headers=other_headers,
    )
    assert ticket.status_code == 404
    cancel = await client.post(f"/api/v1/chat/{run_id}/cancel", headers=other_headers)
    assert cancel.status_code == 404
