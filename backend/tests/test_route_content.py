from uuid import uuid4

import pytest
from conftest import register_user
from sqlalchemy import select

from travel_backend.database import SessionFactory
from travel_backend.errors import APIError
from travel_backend.models import ChatSession, PlanMapPoint, Run, RunEvent, User
from travel_backend.services.runs import process_agent_event


async def create_agent_run(email: str) -> Run:
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == email))
        session = ChatSession(user_id=user.id, summary="Route content")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            agent_run_id=f"agent-{uuid4()}",
            correlation_id=str(uuid4()),
            mode="new_trip",
            input_payload={"message": "Подбери маршрут", "locale": "ru-RU"},
            status="running",
        )
        db.add(run)
        await db.commit()
        return run


def draft_plan(
    map_points: list[dict],
    calendar_events: list[dict] | None = None,
) -> dict:
    return {
        "destination": "IST",
        "start_date": "2026-07-10",
        "end_date": "2026-07-15",
        "selections": {"flight_id": "FL-102", "hotel_id": "HT-045"},
        "decision_rationale": "Маршрут подходит группе.",
        "map_points": map_points,
        "calendar_events": calendar_events or [],
    }


async def test_rich_route_content_is_validated_persisted_and_returned(
    client,
    unique_email,
):
    _, headers = await register_user(client, unique_email)
    run = await create_agent_run(unique_email)
    points = [
        {
            "name": "Гранд-базар",
            "kind": "stop",
            "lat": 41.0107,
            "lng": 28.9681,
            "order": 1,
            "summary": "Исторический рынок в центре Стамбула.",
            "visit_date": "2026-07-11",
            "visit_time": "12:30",
            "visit_start": "2026-07-11T12:30:00+03:00",
            "visit_end": "2026-07-11T14:00:00+03:00",
            "duration_minutes": 90,
            "cost_rub": 1500,
            "price_note": "Без учёта покупок.",
            "calendar_event_ref": "bazaar-visit",
            "ref_id": "place-grand-bazaar",
            "transport_to_next": "Пешком",
            "travel_time_to_next_minutes": 20,
            "distance_to_next_km": 1.4,
            "historical_background": "Рынок развивался на протяжении нескольких веков.",
            "interesting_facts": ["Состоит из множества торговых улиц."],
            "visit_tips": ["Приходить до дневного наплыва посетителей."],
            "food_recommendations": ["Попробовать локальные сладости у проверенных продавцов."],
            "signature_dishes": ["Локум"],
            "average_check_rub": 1200,
            "booking_advice": "Бронирование для посещения рынка не требуется.",
            "accessibility_notes": "Некоторые проходы могут быть тесными.",
            "safety_notes": "Следить за личными вещами в людных местах.",
            "weather_notes": "Большая часть маршрута проходит под крышей.",
            "why_recommended": "Соответствует интересу группы к культуре и местной кухне.",
            "content_source": "agent_rag",
            "content_confidence": "medium",
        },
        {
            "name": "Москва",
            "kind": "origin",
            "lat": 55.7558,
            "lng": 37.6173,
            "order": 0,
            "description": "Точка отправления.",
        },
        {
            "name": "Стамбул",
            "kind": "destination",
            "lat": 41.0082,
            "lng": 28.9784,
            "order": 2,
        },
    ]
    calendar_events = [
        {
            "type": "activity",
            "title": "Посещение Гранд-базара",
            "start": "2026-07-11T12:30:00+03:00",
            "end": "2026-07-11T14:00:00+03:00",
            "location": "Стамбул",
            "route_ref": "bazaar-visit",
        }
    ]

    async with SessionFactory() as db:
        persisted_run = await db.get(Run, run.id)
        await process_agent_event(
            db,
            persisted_run,
            "plan",
            {
                "agent_run_id": persisted_run.agent_run_id,
                "plan": draft_plan(points, calendar_events),
            },
        )
        await db.commit()
        plan_id = persisted_run.active_plan_id
        map_event = await db.scalar(
            select(RunEvent).where(
                RunEvent.run_id == persisted_run.id,
                RunEvent.event_name == "map",
            )
        )
        stored_points = (
            await db.scalars(
                select(PlanMapPoint)
                .where(PlanMapPoint.plan_id == plan_id)
                .order_by(PlanMapPoint.order)
            )
        ).all()

    assert [point.order for point in stored_points] == [0, 1, 2]
    assert all("calendar_event_ref" not in (point.details or {}) for point in stored_points)
    assert all("route_ref" not in (point.details or {}) for point in stored_points)

    map_response = await client.get(f"/api/v1/plans/{plan_id}/map", headers=headers)
    plan_response = await client.get(f"/api/v1/plans/{plan_id}", headers=headers)
    calendar_response = await client.get(f"/api/v1/plans/{plan_id}/calendar", headers=headers)
    assert map_response.status_code == 200
    assert plan_response.status_code == 200
    assert calendar_response.status_code == 200

    api_points = map_response.json()["points"]
    assert plan_response.json()["map_points"] == api_points
    assert map_event.payload["points"] == api_points
    assert [point["order"] for point in api_points] == [0, 1, 2]

    legacy = api_points[0]
    assert legacy["summary"] == "Точка отправления."
    assert legacy["description"] == legacy["summary"]

    rich = api_points[1]
    assert rich["summary"] == "Исторический рынок в центре Стамбула."
    assert rich["visit_date"] == "2026-07-11"
    assert rich["visit_time"] == "12:30"
    assert rich["duration_minutes"] == 90
    assert rich["cost_rub"] == 1500
    assert rich["transport_to_next"] == "Пешком"
    assert rich["travel_time_to_next_minutes"] == 20
    assert rich["distance_to_next_km"] == 1.4
    assert rich["historical_background"].startswith("Рынок")
    assert rich["interesting_facts"] == ["Состоит из множества торговых улиц."]
    assert rich["visit_tips"] == ["Приходить до дневного наплыва посетителей."]
    assert rich["food_recommendations"]
    assert rich["signature_dishes"] == ["Локум"]
    assert rich["average_check_rub"] == 1200
    assert rich["booking_advice"]
    assert rich["accessibility_notes"]
    assert rich["safety_notes"]
    assert rich["weather_notes"]
    assert rich["why_recommended"]
    assert rich["content_source"] == "agent_rag"
    assert rich["content_confidence"] == "medium"
    calendar_event = calendar_response.json()["events"][0]
    assert rich["calendar_event_id"] == calendar_event["id"]
    assert "calendar_event_ref" not in rich
    assert "route_ref" not in calendar_event

    minimal = api_points[2]
    assert set(minimal) == {"id", "name", "kind", "lat", "lng", "order"}


@pytest.mark.parametrize(
    "point_update",
    [
        {"summary": "x" * 1001},
        {"interesting_facts": "not-a-list"},
        {"interesting_facts": ["fact"] * 21},
        {"content_confidence": "certain"},
        {"summary": "canonical", "description": "different"},
        {"unknown_agent_field": "private"},
        {"visit_time": "25:90"},
    ],
)
async def test_invalid_rich_route_content_rejects_complete_plan(
    client,
    unique_email,
    point_update,
):
    await register_user(client, unique_email)
    run = await create_agent_run(unique_email)
    point = {
        "name": "Стамбул",
        "kind": "destination",
        "lat": 41.0082,
        "lng": 28.9784,
        "order": 0,
        **point_update,
    }

    async with SessionFactory() as db:
        persisted_run = await db.get(Run, run.id)
        with pytest.raises(APIError) as captured:
            await process_agent_event(
                db,
                persisted_run,
                "plan",
                {
                    "agent_run_id": persisted_run.agent_run_id,
                    "plan": draft_plan([point]),
                },
            )
        assert captured.value.code == "validation_error"
        await db.rollback()
        stored_points = (
            await db.scalars(select(PlanMapPoint).where(PlanMapPoint.plan_id == run.active_plan_id))
        ).all()
        assert stored_points == []


async def test_unknown_calendar_link_rejects_plan(client, unique_email):
    await register_user(client, unique_email)
    run = await create_agent_run(unique_email)
    point = {
        "name": "Стамбул",
        "kind": "destination",
        "lat": 41.0082,
        "lng": 28.9784,
        "order": 0,
        "calendar_event_ref": "missing-event",
    }

    async with SessionFactory() as db:
        persisted_run = await db.get(Run, run.id)
        with pytest.raises(APIError) as captured:
            await process_agent_event(
                db,
                persisted_run,
                "plan",
                {
                    "agent_run_id": persisted_run.agent_run_id,
                    "plan": draft_plan([point]),
                },
            )
        assert captured.value.code == "validation_error"
        assert captured.value.details["source"] == "agent_map_calendar_link"


async def test_aggregate_route_content_over_one_megabyte_is_rejected(client, unique_email):
    await register_user(client, unique_email)
    run = await create_agent_run(unique_email)
    points = [
        {
            "name": f"Point {index}",
            "kind": "stop",
            "lat": 41.0,
            "lng": 29.0,
            "order": index,
            "interesting_facts": ["x" * 500] * 20,
        }
        for index in range(100)
    ]

    async with SessionFactory() as db:
        persisted_run = await db.get(Run, run.id)
        with pytest.raises(APIError) as captured:
            await process_agent_event(
                db,
                persisted_run,
                "plan",
                {
                    "agent_run_id": persisted_run.agent_run_id,
                    "plan": draft_plan(points),
                },
            )
        assert captured.value.code == "validation_error"
        assert "1 MB" in captured.value.details["reason"]
