from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..errors import APIError
from ..models import GroupMember, Plan, Preference, TravelGroup
from ..schemas import CreateGroupRequest
from ..security import CurrentUser, Database
from ..services.serializers import (
    group_dict,
    group_summary_dict,
    member_dict,
    plan_summary_dict,
    preference_dict,
)

router = APIRouter(prefix="/groups", tags=["Groups"])


async def owned_group(db: Database, user_id: str, group_id: str) -> TravelGroup:
    group = await db.scalar(
        select(TravelGroup)
        .options(
            selectinload(TravelGroup.members).selectinload(GroupMember.preferences)
        )
        .where(
            TravelGroup.id == group_id,
            TravelGroup.owner_id == user_id,
            TravelGroup.is_internal.is_(False),
        )
    )
    if group is None:
        raise APIError(404, "not_found")
    return group


@router.get("")
async def list_groups(
    user: CurrentUser,
    db: Database,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    filters = (TravelGroup.owner_id == user.id, TravelGroup.is_internal.is_(False))
    total = await db.scalar(select(func.count()).select_from(TravelGroup).where(*filters))
    items = (
        await db.scalars(
            select(TravelGroup)
            .options(selectinload(TravelGroup.members))
            .where(*filters)
            .order_by(TravelGroup.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [group_summary_dict(item) for item in items],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201)
async def create_group(body: CreateGroupRequest, user: CurrentUser, db: Database) -> dict:
    group = TravelGroup(
        owner_id=user.id,
        is_internal=False,
        name=body.name.strip(),
        comment=body.comment,
        budget_rub=body.budget_rub,
        origin_city=body.origin_city,
        destination=body.destination,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    db.add(group)
    for source in body.members:
        member = GroupMember(
            group=group,
            full_name=source.full_name,
            age=source.age,
            citizenship=source.citizenship,
            home_airport=source.home_airport,
            role_in_group=source.role_in_group,
            loyalty_program=source.loyalty_program,
            notes=source.notes,
        )
        db.add(member)
        for pref in source.preferences:
            db.add(
                Preference(
                    member=member,
                    type=pref.type,
                    value=pref.value,
                    comment=pref.comment,
                )
            )
    await db.commit()
    return group_dict(await owned_group(db, user.id, group.id))


@router.get("/{group_id}")
async def get_group(group_id: str, user: CurrentUser, db: Database) -> dict:
    return group_dict(await owned_group(db, user.id, group_id))


@router.get("/{group_id}/members")
async def get_members(group_id: str, user: CurrentUser, db: Database) -> dict:
    group = await owned_group(db, user.id, group_id)
    return {"items": [member_dict(member) for member in group.members]}


@router.get("/{group_id}/preferences")
async def get_preferences(group_id: str, user: CurrentUser, db: Database) -> dict:
    group = await owned_group(db, user.id, group_id)
    return {
        "items": [
            {
                "member_id": member.id,
                "full_name": member.full_name,
                "preferences": [preference_dict(pref) for pref in member.preferences],
            }
            for member in group.members
        ]
    }


@router.get("/{group_id}/plans")
async def get_group_plans(group_id: str, user: CurrentUser, db: Database) -> dict:
    await owned_group(db, user.id, group_id)
    plans = (
        await db.scalars(
            select(Plan)
            .where(Plan.group_id == group_id, Plan.user_id == user.id)
            .order_by(Plan.created_at.desc())
        )
    ).all()
    return {"items": [await plan_summary_dict(db, item) for item in plans]}

