from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..clients.agent_service import AgentServiceClient
from ..config import get_settings
from ..database import SessionFactory
from ..errors import APIError
from ..i18n import message
from ..models import (
    ChatSession,
    GroupMember,
    Message,
    Plan,
    PlanCalendarEvent,
    PlanMapPoint,
    Run,
    RunEvent,
    TravelGroup,
    utcnow,
)
from ..schemas import AgentDraftPlan
from .serializers import clean, iso
from .validation import validate_selection

TERMINAL_STATUSES = {"completed", "cancelled", "error"}


async def append_event(
    db: AsyncSession, run_id: str, event_name: str, payload: dict[str, Any]
) -> RunEvent:
    current = await db.scalar(
        select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id)
    )
    event = RunEvent(
        run_id=run_id,
        sequence=(current or 0) + 1,
        event_name=event_name,
        payload=payload,
    )
    db.add(event)
    await db.flush()
    return event


async def ensure_plan(db: AsyncSession, run: Run) -> Plan:
    if run.active_plan_id:
        plan = await db.get(Plan, run.active_plan_id)
        if plan:
            return plan
    session = await db.get(ChatSession, run.session_id)
    plan = Plan(
        user_id=run.user_id,
        session_id=run.session_id,
        group_id=session.group_id if session else None,
        run_id=run.id,
        status="building",
    )
    db.add(plan)
    await db.flush()
    run.active_plan_id = plan.id
    await append_event(
        db,
        run.id,
        "plan_status",
        {"run_id": run.id, "plan_id": plan.id, "status": "building"},
    )
    return plan


async def get_group(db: AsyncSession, group_id: str | None) -> TravelGroup | None:
    if not group_id:
        return None
    return await db.scalar(
        select(TravelGroup)
        .where(TravelGroup.id == group_id)
        .options(
            selectinload(TravelGroup.members).selectinload(GroupMember.preferences)
        )
    )


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


async def persist_draft(
    db: AsyncSession, run: Run, raw_plan: dict[str, Any]
) -> tuple[Plan, dict[str, Any]]:
    try:
        draft = AgentDraftPlan.model_validate(raw_plan)
    except Exception as exc:
        raise APIError(
            422, "validation_error", details={"source": "agent_plan", "reason": str(exc)}
        ) from exc
    session = await db.get(ChatSession, run.session_id)
    group = await get_group(db, session.group_id if session else None)
    validation = await validate_selection(db, group, draft.selections)
    if not validation["valid"]:
        raise APIError(
            422,
            "validation_error",
            details={"hard_violations": validation["hard_violations"]},
        )

    plan = await ensure_plan(db, run)
    await db.execute(delete(PlanMapPoint).where(PlanMapPoint.plan_id == plan.id))
    await db.execute(
        delete(PlanCalendarEvent).where(PlanCalendarEvent.plan_id == plan.id)
    )
    plan.run_id = run.id
    plan.status = "ready"
    plan.destination = draft.destination or (group.destination if group else None)
    plan.start_date = draft.start_date or (group.start_date if group else None)
    plan.end_date = draft.end_date or (group.end_date if group else None)
    plan.decision_rationale = draft.decision_rationale
    plan.estimated_total_rub = validation["calculated_total_rub"]
    plan.flight_id = draft.selections.flight_id
    plan.hotel_id = draft.selections.hotel_id
    plan.tour_id = draft.selections.tour_id
    plan.summary = draft.decision_rationale or "Готовый план поездки"

    points_payload = []
    for index, source in enumerate(draft.map_points):
        try:
            name = str(source["name"])
            kind = source["kind"]
            lat = float(source["lat"])
            lng = float(source["lng"])
            order = int(source.get("order", index))
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(
                422,
                "validation_error",
                details={"source": "agent_map_point", "index": index},
            ) from exc
        if kind not in {"origin", "destination", "stop"}:
            raise APIError(
                422, "validation_error", details={"source": "agent_map_point_kind"}
            )
        if not -90 <= lat <= 90 or not -180 <= lng <= 180:
            raise APIError(
                422, "validation_error", details={"source": "agent_map_coordinates"}
            )
        point = PlanMapPoint(
            plan_id=plan.id,
            name=name,
            kind=kind,
            lat=lat,
            lng=lng,
            order=order,
            note=source.get("note"),
        )
        db.add(point)
        await db.flush()
        points_payload.append(
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
        )

    for index, source in enumerate(draft.calendar_events):
        try:
            event_type = source["type"]
            title = source["title"]
            start = parse_datetime(source["start"])
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(
                422,
                "validation_error",
                details={"source": "agent_calendar_event", "index": index},
            ) from exc
        if event_type not in {"flight", "hotel", "tour", "activity"}:
            raise APIError(422, "validation_error", details={"source": "agent_calendar_type"})
        db.add(
            PlanCalendarEvent(
                plan_id=plan.id,
                type=event_type,
                title=title,
                start=start,
                end=parse_datetime(source["end"]) if source.get("end") else None,
                location=source.get("location"),
                ref_id=source.get("ref_id"),
                notes=source.get("notes"),
            )
        )

    plan_message = Message(
        session_id=run.session_id,
        run_id=run.id,
        role="assistant",
        content="План поездки готов.",
        plan_ref={"plan_id": plan.id, "status": "ready"},
    )
    db.add(plan_message)
    await db.flush()
    await append_event(
        db,
        run.id,
        "plan_status",
        {"run_id": run.id, "plan_id": plan.id, "status": "ready"},
    )
    await append_event(
        db,
        run.id,
        "map",
        {"run_id": run.id, "plan_id": plan.id, "points": points_payload},
    )
    await append_event(
        db,
        run.id,
        "message",
        {
            "run_id": run.id,
            "message": {
                "id": plan_message.id,
                "role": "assistant",
                "content": plan_message.content,
                "created_at": iso(plan_message.created_at),
                "run_id": run.id,
                "plan_ref": plan_message.plan_ref,
            },
        },
    )
    return plan, validation


async def save_assistant_message(
    db: AsyncSession, run: Run, content: str, source_id: str | None = None
) -> None:
    entity = Message(
        id=source_id or None,
        session_id=run.session_id,
        run_id=run.id,
        role="assistant",
        content=content,
    )
    if entity.id is None:
        from ..models import new_id

        entity.id = new_id()
    db.add(entity)
    await db.flush()
    await append_event(
        db,
        run.id,
        "message",
        {
            "run_id": run.id,
            "message": {
                "id": entity.id,
                "role": "assistant",
                "content": entity.content,
                "created_at": iso(entity.created_at),
                "run_id": run.id,
            },
        },
    )


async def process_agent_event(
    db: AsyncSession, run: Run, event_name: str, data: dict[str, Any]
) -> None:
    if event_name == "observability":
        return
    if event_name == "message_delta":
        await append_event(
            db,
            run.id,
            "message_delta",
            {
                "run_id": run.id,
                "message_id": data["message_id"],
                "delta": data["delta"],
            },
        )
    elif event_name == "message":
        source = data["message"]
        await save_assistant_message(db, run, source["content"], source.get("id"))
    elif event_name == "clarifying_question":
        question = data["question"]
        entity = Message(
            session_id=run.session_id,
            run_id=run.id,
            role="assistant",
            content=question["text"],
            question=question,
        )
        db.add(entity)
        await append_event(
            db,
            run.id,
            "clarifying_question",
            {"run_id": run.id, "question": question},
        )
    elif event_name == "plan_status":
        if data.get("status") == "building":
            await ensure_plan(db, run)
        elif data.get("status") == "error":
            plan = await ensure_plan(db, run)
            plan.status = "error"
            await append_event(
                db,
                run.id,
                "plan_status",
                {
                    "run_id": run.id,
                    "plan_id": plan.id,
                    "status": "error",
                    "error": data.get("error") or "Не удалось построить план.",
                },
            )
        # "ready" is deliberately ignored until the draft is validated and persisted.
    elif event_name == "plan":
        await persist_draft(db, run, data["plan"])
    elif event_name == "constraints_conflict":
        await save_assistant_message(
            db, run, data.get("message") or message("constraints_conflict")
        )
    elif event_name == "escalation":
        await save_assistant_message(db, run, data.get("message") or message("escalation"))
    elif event_name == "error":
        run.status = "error"
        run.error_code = data.get("error", {}).get("code", "internal")
        await append_event(
            db,
            run.id,
            "error",
            {
                "run_id": run.id,
                "error": {
                    "code": run.error_code,
                    "message": data.get("error", {}).get(
                        "message", "Произошла ошибка при построении плана."
                    ),
                },
            },
        )
    elif event_name == "run_status":
        status = data["status"]
        run.status = status
        run.outcome = data.get("outcome")
        if status in TERMINAL_STATUSES:
            run.finished_at = utcnow()
        await append_event(
            db,
            run.id,
            "run_status",
            {"run_id": run.id, "status": status},
        )


async def fail_run(db: AsyncSession, run: Run, error: APIError) -> None:
    run.status = "error"
    run.error_code = error.code
    run.finished_at = utcnow()
    if run.active_plan_id:
        plan = await db.get(Plan, run.active_plan_id)
        if plan and plan.status == "building":
            plan.status = "error"
            await append_event(
                db,
                run.id,
                "plan_status",
                {
                    "run_id": run.id,
                    "plan_id": plan.id,
                    "status": "error",
                    "error": message(error.code),
                },
            )
    await append_event(
        db,
        run.id,
        "error",
        {"run_id": run.id, "error": {"code": error.code, "message": message(error.code)}},
    )
    await append_event(
        db, run.id, "run_status", {"run_id": run.id, "status": "error"}
    )


async def execute_run(run_id: str) -> None:
    settings = get_settings()
    client = AgentServiceClient(settings)
    try:
        async with SessionFactory() as db:
            run = await db.get(Run, run_id)
            if run is None:
                return
            session = await db.get(ChatSession, run.session_id)
            payload = {
                "external_run_id": run.id,
                "correlation_id": run.correlation_id,
                "session_id": run.session_id,
                "user_id": run.user_id,
                "mode": run.mode,
                "locale": run.input_payload.get("locale", settings.default_locale),
                **({"thread_id": session.thread_id} if session and session.thread_id else {}),
                **({"group_id": session.group_id} if session and session.group_id else {}),
                **(
                    {"active_plan_id": run.active_plan_id}
                    if run.active_plan_id
                    else {}
                ),
            }
            if run.mode in {"new_trip", "qa"}:
                payload["message"] = run.input_payload["message"]
            elif run.mode == "answer":
                payload["answer"] = run.input_payload["answer"]
            elif run.mode == "modify":
                payload["route_edits"] = run.input_payload["route_edits"]
            try:
                created = await client.create_run(payload, run.correlation_id)
                run.agent_run_id = created.agent_run_id
                if session:
                    session.thread_id = created.thread_id
                run.status = "running"
                await append_event(
                    db, run.id, "run_status", {"run_id": run.id, "status": "running"}
                )
                await db.commit()
                async for event in client.stream(created.stream_url, run.correlation_id):
                    run = await db.get(Run, run_id)
                    if run is None:
                        return
                    if run.status == "cancelled":
                        return
                    await process_agent_event(db, run, event.event, event.data)
                    await db.commit()
                run = await db.get(Run, run_id)
                if run and run.status not in TERMINAL_STATUSES:
                    await fail_run(db, run, APIError(502, "agent_unavailable"))
                    await db.commit()
            except APIError as exc:
                await db.rollback()
                run = await db.get(Run, run_id)
                if run:
                    await fail_run(db, run, exc)
                    await db.commit()
            except Exception:
                await db.rollback()
                run = await db.get(Run, run_id)
                if run:
                    await fail_run(db, run, APIError(500, "internal"))
                    await db.commit()
    finally:
        await client.close()
