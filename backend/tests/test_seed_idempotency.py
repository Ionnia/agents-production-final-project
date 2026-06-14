from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from travel_backend.database import SessionFactory
from travel_backend.models import (
    FlightOffer,
    GroupMember,
    HotelOffer,
    Preference,
    TourOffer,
    TravelGroup,
)
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


async def test_seed_repairs_partial_and_corrupted_data_without_touching_user_groups(database):
    async with SessionFactory() as db:
        flight = await db.get(FlightOffer, "FL-102")
        flight.price_rub = 1
        await db.delete(await db.get(HotelOffer, "HT-045"))
        await db.delete(await db.get(TourOffer, "TR-020"))
        group = await db.scalar(
            select(TravelGroup)
            .where(TravelGroup.id == "G-0001")
            .options(selectinload(TravelGroup.members).selectinload(GroupMember.preferences))
            .execution_options(populate_existing=True)
        )
        group.destination = "CORRUPTED"
        removed_member = group.members[0]
        removed_external_id = removed_member.external_id
        await db.delete(removed_member)
        duplicate = GroupMember(
            group=group,
            external_id=group.members[1].external_id,
            full_name="Duplicate",
            preferences=[Preference(type="duplicate", value="duplicate", comment="duplicate")],
        )
        db.add(duplicate)
        user_group = TravelGroup(
            id="USER-GROUP",
            owner_id=None,
            is_internal=False,
            name="User-owned data",
            destination="KEEP-ME",
            members=[],
        )
        db.add(user_group)
        await db.commit()

        await seed_data(db)
        await seed_data(db)

        assert (await db.get(FlightOffer, "FL-102")).price_rub == 74200
        assert await db.get(HotelOffer, "HT-045") is not None
        assert await db.get(TourOffer, "TR-020") is not None
        repaired = await db.scalar(
            select(TravelGroup)
            .where(TravelGroup.id == "G-0001")
            .options(selectinload(TravelGroup.members).selectinload(GroupMember.preferences))
        )
        assert repaired.destination == "IST"
        assert {member.external_id for member in repaired.members} == {
            "T-0001",
            "T-0002",
            "T-0003",
        }
        assert removed_external_id in {member.external_id for member in repaired.members}
        assert len(repaired.members) == 3
        assert all(
            preference.type != "duplicate"
            for member in repaired.members
            for preference in member.preferences
        )
        untouched = await db.get(TravelGroup, "USER-GROUP")
        assert untouched.destination == "KEEP-ME"
        assert untouched.is_internal is False

        assert await db.scalar(select(func.count()).select_from(FlightOffer)) == 12
        assert await db.scalar(select(func.count()).select_from(HotelOffer)) == 12
        assert await db.scalar(select(func.count()).select_from(TourOffer)) == 3
        assert (
            await db.scalar(
                select(func.count())
                .select_from(TravelGroup)
                .where(TravelGroup.is_internal.is_(True))
            )
            == 6
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(GroupMember)
                .join(TravelGroup)
                .where(TravelGroup.is_internal.is_(True))
            )
            == 11
        )
