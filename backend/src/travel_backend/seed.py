import csv
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import delete, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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


def assign(entity: object, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(entity, key, value)


async def sync_offers(
    db: AsyncSession,
    model: type[FlightOffer] | type[HotelOffer] | type[TourOffer],
    key_name: str,
    values: list[dict[str, Any]],
) -> None:
    keys = [item[key_name] for item in values]
    result = await db.scalars(select(model).where(getattr(model, key_name).in_(keys)))
    existing = {getattr(item, key_name): item for item in result.all()}
    for item in values:
        key = item[key_name]
        entity = existing.get(key)
        if entity is None:
            entity = model()
            db.add(entity)
        assign(entity, item)


def preference_key(source: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    return (
        empty(source["preference_type"]),
        empty(source["preference_value"]),
        empty(source["comment"]),
    )


async def sync_preferences(
    db: AsyncSession,
    member: GroupMember,
    desired_rows: list[dict[str, str]],
) -> None:
    desired = Counter(preference_key(item) for item in desired_rows)
    existing: dict[tuple[str | None, str | None, str | None], list[Preference]] = {}
    for preference in member.preferences:
        key = (preference.type, preference.value, preference.comment)
        existing.setdefault(key, []).append(preference)

    for key, count in desired.items():
        matches = existing.pop(key, [])
        for duplicate in matches[count:]:
            await db.delete(duplicate)
        for _ in range(max(0, count - len(matches))):
            db.add(
                Preference(
                    member=member,
                    type=key[0],
                    value=key[1],
                    comment=key[2],
                )
            )
    for extras in existing.values():
        for preference in extras:
            await db.delete(preference)


async def sync_internal_groups(db: AsyncSession, base: Path) -> None:
    traveler_rows = {item["traveler_id"]: item for item in rows(base / "travelers.csv")}
    memberships: dict[str, list[dict[str, str]]] = {}
    for item in rows(base / "group_members.csv"):
        memberships.setdefault(item["group_id"], []).append(item)
    preferences: dict[str, list[dict[str, str]]] = {}
    for item in rows(base / "traveler_preferences.csv"):
        preferences.setdefault(item["traveler_id"], []).append(item)

    group_rows = rows(base / "travel_groups.csv")
    group_ids = [item["group_id"] for item in group_rows]
    groups = {
        group.id: group
        for group in (
            await db.scalars(
                select(TravelGroup)
                .where(TravelGroup.id.in_(group_ids))
                .options(selectinload(TravelGroup.members).selectinload(GroupMember.preferences))
                .execution_options(populate_existing=True)
            )
        ).all()
    }

    for item in group_rows:
        group = groups.get(item["group_id"])
        if group is None:
            group = TravelGroup(id=item["group_id"], members=[])
            db.add(group)
            groups[group.id] = group
        assign(
            group,
            {
                "owner_id": None,
                "is_internal": True,
                "name": f"Сценарная группа {item['group_id']}",
                "comment": empty(item["group_comment"]),
                "budget_rub": int(item["budget_rub"]),
                "origin_city": empty(item["origin_city"]),
                "destination": empty(item["destination"]),
                "start_date": date.fromisoformat(item["start_date"]),
                "end_date": date.fromisoformat(item["end_date"]),
            },
        )
        await db.flush()

        desired_links = {link["traveler_id"]: link for link in memberships.get(group.id, [])}
        existing_members: dict[str, list[GroupMember]] = {}
        for member in group.members:
            if member.external_id and not inspect(member).deleted:
                existing_members.setdefault(member.external_id, []).append(member)

        for traveler_id, link in desired_links.items():
            candidates = existing_members.pop(traveler_id, [])
            member = candidates[0] if candidates else GroupMember(group=group, preferences=[])
            db.add(member)
            for duplicate in candidates[1:]:
                await db.delete(duplicate)
            source = traveler_rows[traveler_id]
            assign(
                member,
                {
                    "external_id": traveler_id,
                    "full_name": source["full_name"],
                    "age": int(source["age"]) if source["age"] else None,
                    "citizenship": empty(source["citizenship"]),
                    "home_airport": empty(source["home_airport"]),
                    "role_in_group": empty(link["role_in_group"]),
                    "loyalty_program": empty(source["loyalty_program"]),
                    "notes": empty(source["notes"]),
                },
            )
            await db.flush()
            await sync_preferences(db, member, preferences.get(traveler_id, []))

        for extras in existing_members.values():
            for member in extras:
                await db.delete(member)
        await db.execute(
            delete(GroupMember).where(
                GroupMember.group_id == group.id,
                GroupMember.external_id.is_(None),
            )
        )


async def seed_data(db: AsyncSession) -> None:
    settings = get_settings()
    base = settings.data_dir / "travelers"
    try:
        await sync_offers(
            db,
            FlightOffer,
            "flight_id",
            [
                {
                    "flight_id": item["flight_id"],
                    "origin_city": item["origin_city"],
                    "destination": item["destination"],
                    "price_rub": int(item["price_rub"]),
                    "baggage_included": item["baggage_included"] == "1",
                    "stops": int(item["stops"]),
                    "departure_time": item["departure_time"],
                    "arrival_time": item["arrival_time"],
                    "fare_type": item["fare_type"],
                    "notes": empty(item["notes"]),
                }
                for item in rows(base / "flights.csv")
            ],
        )
        await sync_offers(
            db,
            HotelOffer,
            "hotel_id",
            [
                {
                    "hotel_id": item["hotel_id"],
                    "destination": item["destination"],
                    "stars": int(item["stars"]),
                    "price_per_night_rub": int(item["price_per_night_rub"]),
                    "breakfast_included": item["breakfast_included"] == "1",
                    "free_cancellation": item["free_cancellation"] == "1",
                    "rating": float(item["rating"]),
                    "notes": empty(item["notes"]),
                }
                for item in rows(base / "hotels.csv")
            ],
        )
        await sync_offers(
            db,
            TourOffer,
            "tour_id",
            [
                {
                    "tour_id": item["tour_id"],
                    "destination": item["destination"],
                    "total_price_rub": int(item["total_price_rub"]),
                    "includes_flight": item["includes_flight"] == "1",
                    "includes_transfer": item["includes_transfer"] == "1",
                    "hotel_id": empty(item["hotel_id"]),
                    "notes": empty(item["notes"]),
                }
                for item in rows(base / "tours.csv")
            ],
        )
        await sync_internal_groups(db, base)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
