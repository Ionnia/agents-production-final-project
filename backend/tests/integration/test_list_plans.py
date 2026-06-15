from conftest import register_user
from sqlalchemy import select

from travel_backend.database import SessionFactory
from travel_backend.models import ChatSession, Plan, Run, User


async def test_list_plans_includes_group_less_plans(client, unique_email):
    """A plan with no group (the inline-chat approval default) must still be listed
    by GET /plans — the per-group endpoint can never return it."""
    _, headers = await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Поездка в Стамбул")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id="list-plans-test",
            mode="new_trip",
            input_payload={"message": "Подбери поездку"},
            status="completed",
        )
        db.add(run)
        await db.flush()
        plan = Plan(
            user_id=user.id,
            session_id=session.id,
            group_id=None,  # group-less, as inline-chat plans are
            run_id=run.id,
            status="accepted",
            destination="Стамбул",
            estimated_total_rub=120000,
        )
        db.add(plan)
        await db.commit()
        plan_id = plan.id

    listed = await client.get("/api/v1/plans", headers=headers)
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert any(item["plan_id"] == plan_id for item in items)
    assert {item["plan_id"]: item["status"] for item in items}[plan_id] == "accepted"


async def test_list_plans_is_scoped_to_the_current_user(client, unique_email):
    _, headers = await register_user(client, unique_email)
    listed = await client.get("/api/v1/plans", headers=headers)
    assert listed.status_code == 200
    # A fresh user owns no plans; seed plans belong to other users and must not leak.
    assert listed.json()["items"] == []
