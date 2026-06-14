import csv
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import (
    FlightOffer,
    GroupMember,
    HotelOffer,
    Preference,
    TourOffer,
    TravelGroup,
)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def empty(value: str | None) -> str | None:
    return value if value else None


async def seed_data(db: AsyncSession) -> None:
    settings = get_settings()
    base = settings.data_dir / "travelers"
    existing = await db.scalar(select(func.count()).select_from(FlightOffer))
    if existing:
        return

    for item in rows(base / "flights.csv"):
        db.add(
            FlightOffer(
                flight_id=item["flight_id"],
                origin_city=item["origin_city"],
                destination=item["destination"],
                price_rub=int(item["price_rub"]),
                baggage_included=item["baggage_included"] == "1",
                stops=int(item["stops"]),
                departure_time=item["departure_time"],
                arrival_time=item["arrival_time"],
                fare_type=item["fare_type"],
                notes=empty(item["notes"]),
            )
        )
    for item in rows(base / "hotels.csv"):
        db.add(
            HotelOffer(
                hotel_id=item["hotel_id"],
                destination=item["destination"],
                stars=int(item["stars"]),
                price_per_night_rub=int(item["price_per_night_rub"]),
                breakfast_included=item["breakfast_included"] == "1",
                free_cancellation=item["free_cancellation"] == "1",
                rating=float(item["rating"]),
                notes=empty(item["notes"]),
            )
        )
    for item in rows(base / "tours.csv"):
        db.add(
            TourOffer(
                tour_id=item["tour_id"],
                destination=item["destination"],
                total_price_rub=int(item["total_price_rub"]),
                includes_flight=item["includes_flight"] == "1",
                includes_transfer=item["includes_transfer"] == "1",
                hotel_id=empty(item["hotel_id"]),
                notes=empty(item["notes"]),
            )
        )

    traveler_rows = {item["traveler_id"]: item for item in rows(base / "travelers.csv")}
    membership: dict[str, list[dict[str, str]]] = {}
    for item in rows(base / "group_members.csv"):
        membership.setdefault(item["group_id"], []).append(item)
    preferences: dict[str, list[dict[str, str]]] = {}
    for item in rows(base / "traveler_preferences.csv"):
        preferences.setdefault(item["traveler_id"], []).append(item)

    for item in rows(base / "travel_groups.csv"):
        group = TravelGroup(
            id=item["group_id"],
            owner_id=None,
            is_internal=True,
            name=f"Сценарная группа {item['group_id']}",
            comment=empty(item["group_comment"]),
            budget_rub=int(item["budget_rub"]),
            origin_city=empty(item["origin_city"]),
            destination=empty(item["destination"]),
            start_date=date.fromisoformat(item["start_date"]),
            end_date=date.fromisoformat(item["end_date"]),
        )
        db.add(group)
        for link in membership.get(group.id, []):
            source = traveler_rows[link["traveler_id"]]
            member = GroupMember(
                external_id=source["traveler_id"],
                group=group,
                full_name=source["full_name"],
                age=int(source["age"]) if source["age"] else None,
                citizenship=empty(source["citizenship"]),
                home_airport=empty(source["home_airport"]),
                role_in_group=empty(link["role_in_group"]),
                loyalty_program=empty(source["loyalty_program"]),
                notes=empty(source["notes"]),
            )
            db.add(member)
            for pref in preferences.get(source["traveler_id"], []):
                db.add(
                    Preference(
                        member=member,
                        type=empty(pref["preference_type"]),
                        value=empty(pref["preference_value"]),
                        comment=empty(pref["comment"]),
                    )
                )
    await db.commit()
