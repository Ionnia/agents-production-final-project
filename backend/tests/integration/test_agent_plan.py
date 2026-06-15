from conftest import register_user
from sqlalchemy import select

from travel_backend.database import SessionFactory
from travel_backend.models import ChatSession, Plan, Run, RunEvent, User
from travel_backend.services.runs import process_agent_event


async def test_agent_ready_is_gated_until_valid_draft_is_persisted(client, unique_email):
    await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(
            user_id=user.id,
            group_id="G-0001",
            summary="Поездка в Стамбул",
        )
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            group_id="G-0001",
            correlation_id="agent-plan-test",
            mode="new_trip",
            input_payload={"message": "Подбери поездку"},
            status="running",
        )
        db.add(run)
        await db.flush()

        await process_agent_event(
            db, run, "plan_status", {"agent_run_id": "a-1", "status": "ready"}
        )
        premature_ready = (
            await db.scalars(
                select(RunEvent).where(
                    RunEvent.run_id == run.id,
                    RunEvent.event_name == "plan_status",
                )
            )
        ).all()
        assert premature_ready == []

        await process_agent_event(
            db,
            run,
            "plan",
            {
                "agent_run_id": "a-1",
                "plan": {
                    "destination": "IST",
                    "start_date": "2026-07-10",
                    "end_date": "2026-07-15",
                    "selections": {"flight_id": "FL-102", "hotel_id": "HT-045"},
                    "estimated_total_rub": 1,
                    "decision_rationale": "Подходит семье и укладывается в бюджет.",
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
                    "calendar_events": [
                        {
                            "type": "flight",
                            "title": "Перелёт в Стамбул",
                            "start": "2026-07-10T10:20:00+03:00",
                            "ref_id": "FL-102",
                        }
                    ],
                },
            },
        )
        await db.commit()

        plan = await db.get(Plan, run.active_plan_id)
        assert plan.status == "ready"
        assert plan.estimated_total_rub == 130500
        events = (
            await db.scalars(
                select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.sequence)
            )
        ).all()
        assert [event.event_name for event in events] == [
            "plan_status",
            "plan_status",
            "map",
            "message",
        ]
        assert events[0].payload["status"] == "building"
        assert events[1].payload["status"] == "ready"
        assert all(point["id"] for point in events[2].payload["points"])


async def test_group_less_plan_persists_and_uses_draft_dates_for_nights(client, unique_email):
    # The reported flow has no pre-selected group: a free-form chat plan must still validate,
    # persist as ready, and price the hotel over the draft's trip length (not a single night).
    await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Стамбул из переписки")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id="agent-plan-groupless",
            mode="new_trip",
            input_payload={"message": "Стамбул, 5–15 июля, вылет из Москвы"},
            status="running",
        )
        db.add(run)
        await db.flush()

        await process_agent_event(
            db,
            run,
            "plan",
            {
                "agent_run_id": "a-2",
                "plan": {
                    "destination": "Стамбул",
                    "start_date": "2026-07-05",
                    "end_date": "2026-07-15",  # 10 nights
                    "selections": {"flight_id": "FL-102", "hotel_id": "HT-045"},
                    "decision_rationale": "Перелёт и отель в Стамбуле.",
                    "map_points": [
                        {"name": "Москва", "kind": "origin", "lat": 55.7558, "lng": 37.6173, "order": 0},
                        {"name": "Стамбул", "kind": "destination", "lat": 41.0082, "lng": 28.9784, "order": 1},
                    ],
                },
            },
        )
        await db.commit()

        plan = await db.get(Plan, run.active_plan_id)
        assert plan.status == "ready"
        assert plan.group_id is None
        # flight 74200 + hotel 11260 * 10 nights = 186800 (single-night default would be 85460).
        assert plan.estimated_total_rub == 74200 + 11260 * 10
