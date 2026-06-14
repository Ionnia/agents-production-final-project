from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    ChatSession,
    FlightOffer,
    GroupMember,
    HotelOffer,
    Plan,
    PlanCalendarEvent,
    PlanMapPoint,
    Preference,
    TourOffer,
    TravelGroup,
)


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "tzinfo") and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def clean(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def preference_dict(item: Preference) -> dict[str, Any]:
    return clean(
        {"id": item.id, "type": item.type, "value": item.value, "comment": item.comment}
    )


def member_dict(item: GroupMember) -> dict[str, Any]:
    return clean(
        {
            "id": item.id,
            "full_name": item.full_name,
            "age": item.age,
            "citizenship": item.citizenship,
            "home_airport": item.home_airport,
            "role_in_group": item.role_in_group,
            "loyalty_program": item.loyalty_program,
            "notes": item.notes,
            "preferences": [preference_dict(pref) for pref in item.preferences],
        }
    )


def group_dict(item: TravelGroup) -> dict[str, Any]:
    return clean(
        {
            "id": item.id,
            "name": item.name,
            "comment": item.comment,
            "budget_rub": item.budget_rub,
            "origin_city": item.origin_city,
            "destination": item.destination,
            "start_date": iso(item.start_date),
            "end_date": iso(item.end_date),
            "created_at": iso(item.created_at),
            "updated_at": iso(item.updated_at),
            "members": [member_dict(member) for member in item.members],
        }
    )


def group_summary_dict(item: TravelGroup) -> dict[str, Any]:
    return clean(
        {
            "id": item.id,
            "name": item.name,
            "comment": item.comment,
            "budget_rub": item.budget_rub,
            "destination": item.destination,
            "member_count": len(item.members),
            "created_at": iso(item.created_at),
        }
    )


def flight_dict(item: FlightOffer) -> dict[str, Any]:
    return clean(
        {
            "flight_id": item.flight_id,
            "origin_city": item.origin_city,
            "destination": item.destination,
            "price_rub": item.price_rub,
            "baggage_included": item.baggage_included,
            "stops": item.stops,
            "departure_time": item.departure_time,
            "arrival_time": item.arrival_time,
            "fare_type": item.fare_type,
            "notes": item.notes,
        }
    )


def hotel_dict(item: HotelOffer, nights: int | None = None) -> dict[str, Any]:
    data = {
        "hotel_id": item.hotel_id,
        "destination": item.destination,
        "stars": item.stars,
        "price_per_night_rub": item.price_per_night_rub,
        "breakfast_included": item.breakfast_included,
        "free_cancellation": item.free_cancellation,
        "rating": item.rating,
        "notes": item.notes,
    }
    if nights is not None:
        data["nights"] = nights
    return clean(data)


def tour_dict(item: TourOffer) -> dict[str, Any]:
    return clean(
        {
            "tour_id": item.tour_id,
            "destination": item.destination,
            "total_price_rub": item.total_price_rub,
            "includes_flight": item.includes_flight,
            "includes_transfer": item.includes_transfer,
            "hotel_id": item.hotel_id,
            "notes": item.notes,
        }
    )


async def plan_dict(db: AsyncSession, item: Plan) -> dict[str, Any]:
    flight = await db.get(FlightOffer, item.flight_id) if item.flight_id else None
    hotel = await db.get(HotelOffer, item.hotel_id) if item.hotel_id else None
    tour = await db.get(TourOffer, item.tour_id) if item.tour_id else None
    points = (
        await db.scalars(
            select(PlanMapPoint)
            .where(PlanMapPoint.plan_id == item.id)
            .order_by(PlanMapPoint.order)
        )
    ).all()
    nights = (
        (item.end_date - item.start_date).days
        if item.start_date is not None and item.end_date is not None
        else 1
    )
    return clean(
        {
            "id": item.id,
            "session_id": item.session_id,
            "group_id": item.group_id,
            "run_id": item.run_id,
            "status": item.status,
            "summary": item.summary,
            "destination": item.destination,
            "start_date": iso(item.start_date),
            "end_date": iso(item.end_date),
            "decision_rationale": item.decision_rationale,
            "estimated_total_rub": item.estimated_total_rub,
            "items": clean(
                {
                    "flight": flight_dict(flight) if flight else None,
                    "hotel": hotel_dict(hotel, nights) if hotel else None,
                    "tour": tour_dict(tour) if tour else None,
                }
            ),
            "map_points": [
                clean(
                    {
                        "id": point.id,
                        "name": point.name,
                        "kind": point.kind,
                        "lat": point.lat,
                        "lng": point.lng,
                        "order": point.order,
                        "note": point.note,
                    }
                )
                for point in points
            ],
            "created_at": iso(item.created_at),
            "updated_at": iso(item.updated_at),
        }
    )


async def plan_summary_dict(db: AsyncSession, item: Plan) -> dict[str, Any]:
    return clean(
        {
            "plan_id": item.id,
            "status": item.status,
            "destination": item.destination,
            "estimated_total_rub": item.estimated_total_rub,
            "created_at": iso(item.created_at),
        }
    )


def session_summary_dict(
    item: ChatSession,
    last_preview: str | None,
    latest_plan: Plan | None,
) -> dict[str, Any]:
    return clean(
        {
            "id": item.id,
            "summary": item.summary,
            "created_at": iso(item.created_at),
            "updated_at": iso(item.updated_at),
            "last_message_preview": last_preview,
            "group_id": item.group_id,
            "latest_plan_id": latest_plan.id if latest_plan else None,
            "plan_status": latest_plan.status if latest_plan else None,
        }
    )


async def calendar_dict(db: AsyncSession, plan_id: str) -> dict[str, Any]:
    events = (
        await db.scalars(
            select(PlanCalendarEvent)
            .where(PlanCalendarEvent.plan_id == plan_id)
            .order_by(PlanCalendarEvent.start)
        )
    ).all()
    return {
        "plan_id": plan_id,
        "timezone": "Europe/Moscow",
        "events": [
            clean(
                {
                    "id": event.id,
                    "type": event.type,
                    "title": event.title,
                    "start": iso(event.start),
                    "end": iso(event.end),
                    "location": event.location,
                    "ref_id": event.ref_id,
                    "notes": event.notes,
                }
            )
            for event in events
        ],
    }

