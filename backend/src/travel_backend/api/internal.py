from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..errors import APIError
from ..models import FlightOffer, GroupMember, HotelOffer, TourOffer, TravelGroup
from ..schemas import (
    FlightSearchRequest,
    HotelSearchRequest,
    TourSearchRequest,
    ValidatePlanRequest,
)
from ..security import Database, require_tool_auth
from ..services.serializers import flight_dict, hotel_dict, tour_dict
from ..services.validation import validate_selection

router = APIRouter(
    prefix="/internal",
    tags=["Internal"],
    dependencies=[Depends(require_tool_auth)],
)


async def any_group(db: Database, group_id: str) -> TravelGroup:
    group = await db.scalar(
        select(TravelGroup)
        .options(selectinload(TravelGroup.members).selectinload(GroupMember.preferences))
        .where(TravelGroup.id == group_id)
    )
    if group is None:
        raise APIError(404, "not_found")
    return group


@router.get("/groups/{group_id}/context")
async def group_context(group_id: str, db: Database) -> dict:
    group = await any_group(db, group_id)
    return {
        "group_id": group.id,
        **({"origin_city": group.origin_city} if group.origin_city else {}),
        **({"destination": group.destination} if group.destination else {}),
        **({"start_date": group.start_date.isoformat()} if group.start_date else {}),
        **({"end_date": group.end_date.isoformat()} if group.end_date else {}),
        **({"budget_rub": group.budget_rub} if group.budget_rub is not None else {}),
        "members": [
            {
                "traveler_id": member.external_id or member.id,
                "full_name": member.full_name,
                **({"age": member.age} if member.age is not None else {}),
                **({"citizenship": member.citizenship} if member.citizenship else {}),
                **({"home_airport": member.home_airport} if member.home_airport else {}),
                **({"role_in_group": member.role_in_group} if member.role_in_group else {}),
                **({"loyalty_program": member.loyalty_program} if member.loyalty_program else {}),
                "preferences": [
                    {
                        **({"type": pref.type} if pref.type else {}),
                        **({"value": pref.value} if pref.value else {}),
                        **({"comment": pref.comment} if pref.comment else {}),
                    }
                    for pref in member.preferences
                ],
                **({"notes": member.notes} if member.notes else {}),
            }
            for member in group.members
        ],
        **({"history_summary": group.comment} if group.comment else {}),
    }


@router.post("/flights/search")
async def search_flights(body: FlightSearchRequest, db: Database) -> dict:
    query = select(FlightOffer).where(
        FlightOffer.origin_city == body.origin,
        FlightOffer.destination == body.destination,
    )
    if body.required_baggage:
        query = query.where(FlightOffer.baggage_included.is_(True))
    if body.max_stops is not None:
        query = query.where(FlightOffer.stops <= body.max_stops)
    if body.budget_rub is not None:
        query = query.where(FlightOffer.price_rub <= body.budget_rub)
    if body.avoid_night_arrival:
        query = query.where(FlightOffer.arrival_time < "23:00", FlightOffer.arrival_time >= "05:00")
    items = (await db.scalars(query.order_by(FlightOffer.price_rub))).all()
    return {"items": [flight_dict(item) for item in items]}


@router.post("/hotels/search")
async def search_hotels(body: HotelSearchRequest, db: Database) -> dict:
    query = select(HotelOffer).where(HotelOffer.destination == body.destination)
    if body.breakfast_required:
        query = query.where(HotelOffer.breakfast_included.is_(True))
    if body.free_cancellation_preferred:
        query = query.where(HotelOffer.free_cancellation.is_(True))
    if body.min_stars is not None:
        query = query.where(HotelOffer.stars >= body.min_stars)
    if body.budget_per_night_rub is not None:
        query = query.where(HotelOffer.price_per_night_rub <= body.budget_per_night_rub)
    items = (await db.scalars(query.order_by(HotelOffer.price_per_night_rub))).all()
    return {"items": [hotel_dict(item) for item in items]}


@router.post("/tours/search")
async def search_tours(body: TourSearchRequest, db: Database) -> dict:
    query = select(TourOffer).where(TourOffer.destination == body.destination)
    if body.budget_rub is not None:
        query = query.where(TourOffer.total_price_rub <= body.budget_rub)
    if body.includes_flight is not None:
        query = query.where(TourOffer.includes_flight == body.includes_flight)
    if body.includes_transfer is not None:
        query = query.where(TourOffer.includes_transfer == body.includes_transfer)
    items = (await db.scalars(query.order_by(TourOffer.total_price_rub))).all()
    return {"items": [tour_dict(item) for item in items]}


@router.post("/plans/validate")
async def validate_plan(body: ValidatePlanRequest, db: Database) -> dict:
    group = await any_group(db, body.group_id)
    result = await validate_selection(db, group, body.plan, body.constraints)
    result.pop("calculated_total_rub", None)
    if result["budget_left_rub"] is None:
        result.pop("budget_left_rub")
    return result
