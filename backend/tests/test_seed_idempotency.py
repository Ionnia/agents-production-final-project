from sqlalchemy import func, select

from travel_backend.database import SessionFactory
from travel_backend.models import FlightOffer, GroupMember, TravelGroup
from travel_backend.seed import seed_data


async def test_seed_is_idempotent_and_loads_members_and_preferences(database):
    async with SessionFactory() as db:
        internal_members = (
            select(func.count())
            .select_from(GroupMember)
            .join(TravelGroup)
            .where(TravelGroup.is_internal.is_(True))
        )
        before = {
            "flights": await db.scalar(select(func.count()).select_from(FlightOffer)),
            "groups": await db.scalar(select(func.count()).select_from(TravelGroup)),
            "internal_members": await db.scalar(internal_members),
        }
        await seed_data(db)
        after = {
            "flights": await db.scalar(select(func.count()).select_from(FlightOffer)),
            "groups": await db.scalar(select(func.count()).select_from(TravelGroup)),
            "internal_members": await db.scalar(internal_members),
        }
        assert (
            before
            == after
            == {
                "flights": 12,
                "groups": before["groups"],
                "internal_members": 11,
            }
        )
        assert before["groups"] >= 6
        group = await db.get(TravelGroup, "G-0001")
        assert len(group.members) == 3
        assert any(member.preferences for member in group.members)
