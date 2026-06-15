from fastapi import APIRouter
from sqlalchemy import select

from ..errors import APIError
from ..models import Plan, PlanMapPoint
from ..schemas import RejectRequest
from ..security import CurrentUser, Database
from ..services.serializers import calendar_dict, map_point_dict, plan_dict, plan_summary_dict

router = APIRouter(prefix="/plans", tags=["Plans"])


async def owned_plan(db: Database, user_id: str, plan_id: str) -> Plan:
    plan = await db.scalar(select(Plan).where(Plan.id == plan_id, Plan.user_id == user_id))
    if plan is None:
        raise APIError(404, "not_found")
    return plan


@router.get("")
async def list_plans(user: CurrentUser, db: Database) -> dict:
    # Every plan owned by the user, newest first. Unlike `/groups/{id}/plans`, this
    # is NOT scoped to a group, so group-less plans (the default for the inline-chat
    # approval flow) are listed here — otherwise they would be unreachable.
    plans = (
        await db.scalars(
            select(Plan).where(Plan.user_id == user.id).order_by(Plan.created_at.desc())
        )
    ).all()
    return {"items": [await plan_summary_dict(db, item) for item in plans]}


@router.get("/{plan_id}")
async def get_plan(plan_id: str, user: CurrentUser, db: Database) -> dict:
    return await plan_dict(db, await owned_plan(db, user.id, plan_id))


@router.post("/{plan_id}/accept")
async def accept_plan(plan_id: str, user: CurrentUser, db: Database) -> dict:
    plan = await owned_plan(db, user.id, plan_id)
    if plan.status != "ready":
        raise APIError(409, "plan_not_ready")
    plan.status = "accepted"
    await db.commit()
    return await plan_dict(db, plan)


@router.post("/{plan_id}/reject")
async def reject_plan(
    plan_id: str,
    user: CurrentUser,
    db: Database,
    body: RejectRequest | None = None,
) -> dict:
    plan = await owned_plan(db, user.id, plan_id)
    plan.status = "rejected"
    plan.rejection_reason = body.reason if body else None
    await db.commit()
    return await plan_dict(db, plan)


@router.get("/{plan_id}/map")
async def get_map(plan_id: str, user: CurrentUser, db: Database) -> dict:
    plan = await owned_plan(db, user.id, plan_id)
    points = (
        await db.scalars(
            select(PlanMapPoint).where(PlanMapPoint.plan_id == plan.id).order_by(PlanMapPoint.order)
        )
    ).all()
    serialized = [map_point_dict(item) for item in points]
    response = {
        "plan_id": plan.id,
        "status": plan.status,
        "editable": plan.status == "ready",
        "points": serialized,
    }
    if points:
        response["bounds"] = {
            "north": max(point.lat for point in points),
            "south": min(point.lat for point in points),
            "east": max(point.lng for point in points),
            "west": min(point.lng for point in points),
        }
    return response


@router.get("/{plan_id}/calendar")
async def get_calendar(plan_id: str, user: CurrentUser, db: Database) -> dict:
    plan = await owned_plan(db, user.id, plan_id)
    return await calendar_dict(db, plan.id)
