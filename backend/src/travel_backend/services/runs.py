from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..clients.agent_service import AgentServiceClient, CreatedRun
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
from .serializers import iso, map_point_dict
from .validation import validate_selection

TERMINAL_STATUSES = {"completed", "cancelled", "error"}
PUBLIC_ERROR_CODES = {
    "validation_error",
    "unauthorized",
    "token_expired",
    "forbidden",
    "not_found",
    "conflict",
    "plan_not_ready",
    "rate_limited",
    "agent_unavailable",
    "timeout",
    "internal",
}
AGENT_EVENT_FIELDS = {
    "run_status": {"status"},
    "message_delta": {"message_id", "delta"},
    "message": {"message"},
    "clarifying_question": {"question"},
    "plan_status": {"status"},
    "plan": {"plan"},
    "constraints_conflict": {"message", "suggested_relaxations"},
    "escalation": {"reason", "message"},
    "observability": {"kind"},
    "error": {"error"},
}


def run_locale(run: Run) -> str:
    return run.input_payload.get("locale", get_settings().default_locale)


def safe_message(code: str, locale: str) -> str:
    translated = message(code, locale)
    return message("internal", locale) if translated == code else translated


def validate_agent_event(run: Run, event_name: str, data: dict[str, Any]) -> None:
    required = AGENT_EVENT_FIELDS.get(event_name)
    if required is None or not isinstance(data, dict):
        raise APIError(422, "validation_error", details={"source": "agent_event"})
    if not isinstance(data.get("agent_run_id"), str):
        raise APIError(422, "validation_error", details={"source": "agent_run_id"})
    if run.agent_run_id and data["agent_run_id"] != run.agent_run_id:
        raise APIError(422, "validation_error", details={"source": "agent_run_id_mismatch"})
    if not required <= data.keys():
        raise APIError(422, "validation_error", details={"source": "agent_event_fields"})

    if event_name == "run_status" and data["status"] not in {
        "started",
        "running",
        "completed",
        "cancelled",
        "error",
    }:
        raise APIError(422, "validation_error", details={"source": "agent_run_status"})
    if event_name == "run_status" and data.get("outcome") not in {
        None,
        "recommendation",
        "clarification",
        "constraints_conflict",
        "escalation",
    }:
        raise APIError(422, "validation_error", details={"source": "agent_run_outcome"})
    if event_name == "plan_status" and data["status"] not in {"building", "ready", "error"}:
        raise APIError(422, "validation_error", details={"source": "agent_plan_status"})
    if event_name == "message":
        source = data["message"]
        if (
            not isinstance(source, dict)
            or source.get("role") != "assistant"
            or not isinstance(source.get("id"), str)
            or not isinstance(source.get("content"), str)
        ):
            raise APIError(422, "validation_error", details={"source": "agent_message"})
    if event_name == "message_delta" and not all(
        isinstance(data.get(key), str) for key in ("message_id", "delta")
    ):
        raise APIError(422, "validation_error", details={"source": "agent_message_delta"})
    if event_name == "clarifying_question":
        question = data["question"]
        if (
            not isinstance(question, dict)
            or not isinstance(question.get("id"), str)
            or not isinstance(question.get("text"), str)
            or not isinstance(question.get("options"), list)
            or not isinstance(question.get("allow_freeform"), bool)
            or not all(
                isinstance(option, dict)
                and isinstance(option.get("id"), str)
                and isinstance(option.get("label"), str)
                for option in question.get("options", [])
            )
        ):
            raise APIError(422, "validation_error", details={"source": "agent_question"})
    if event_name == "constraints_conflict" and (
        not isinstance(data["message"], str)
        or not isinstance(data["suggested_relaxations"], list)
        or not all(isinstance(item, str) for item in data["suggested_relaxations"])
    ):
        raise APIError(422, "validation_error", details={"source": "agent_conflict"})
    if event_name == "escalation" and not all(
        isinstance(data.get(key), str) for key in ("reason", "message")
    ):
        raise APIError(422, "validation_error", details={"source": "agent_escalation"})
    if event_name == "observability" and data["kind"] not in {
        "node_started",
        "node_finished",
        "tool_call",
        "tool_result",
        "tool_error",
    }:
        raise APIError(422, "validation_error", details={"source": "agent_observability"})
    if event_name == "error":
        error = data["error"]
        if (
            not isinstance(error, dict)
            or not isinstance(error.get("code"), str)
            or not isinstance(error.get("message"), str)
        ):
            raise APIError(422, "validation_error", details={"source": "agent_error"})


async def append_event(
    db: AsyncSession, run_id: str, event_name: str, payload: dict[str, Any]
) -> RunEvent:
    current = await db.scalar(select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id))
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
        .options(selectinload(TravelGroup.members).selectinload(GroupMember.preferences))
    )


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
    if group and group.destination and draft.destination and draft.destination != group.destination:
        validation["valid"] = False
        validation["hard_violations"].append(
            {
                "code": "plan_destination_mismatch",
                "message": "Направление плана не соответствует направлению группы.",
            }
        )
    if not validation["valid"]:
        raise APIError(
            422,
            "validation_error",
            details={"hard_violations": validation["hard_violations"]},
        )

    plan = await ensure_plan(db, run)
    await db.execute(delete(PlanMapPoint).where(PlanMapPoint.plan_id == plan.id))
    await db.execute(delete(PlanCalendarEvent).where(PlanCalendarEvent.plan_id == plan.id))
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

    calendar_event_ids: dict[str, str] = {}
    for source in draft.calendar_events:
        event = PlanCalendarEvent(
            plan_id=plan.id,
            type=source.type,
            title=source.title,
            start=source.start,
            end=source.end,
            location=source.location,
            ref_id=source.ref_id,
            notes=source.notes,
        )
        db.add(event)
        await db.flush()
        if source.route_ref:
            calendar_event_ids[source.route_ref] = event.id

    points_payload = []
    for index, source in enumerate(sorted(draft.map_points, key=lambda item: item.order)):
        calendar_event_id = None
        if source.calendar_event_ref:
            calendar_event_id = calendar_event_ids.get(source.calendar_event_ref)
            if calendar_event_id is None:
                raise APIError(
                    422,
                    "validation_error",
                    details={
                        "source": "agent_map_calendar_link",
                        "index": index,
                    },
                )
        details = source.public_details(calendar_event_id)
        point = PlanMapPoint(
            plan_id=plan.id,
            name=source.name,
            kind=source.kind,
            lat=source.lat,
            lng=source.lng,
            order=source.order,
            note=source.note,
            details=details or None,
        )
        db.add(point)
        await db.flush()
        points_payload.append(map_point_dict(point))

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
    db: AsyncSession, run: Run, content: str, agent_message_id: str | None = None
) -> Message:
    entity = None
    if agent_message_id:
        entity = await db.scalar(
            select(Message).where(
                Message.run_id == run.id,
                Message.agent_message_id == agent_message_id,
                Message.role == "assistant",
            )
        )
    if entity is None:
        entity = Message(
            agent_message_id=agent_message_id,
            session_id=run.session_id,
            run_id=run.id,
            role="assistant",
            content=content,
        )
        db.add(entity)
    else:
        entity.content = content
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
    return entity


async def append_assistant_delta(
    db: AsyncSession, run: Run, agent_message_id: str, delta: str
) -> None:
    entity = await db.scalar(
        select(Message).where(
            Message.run_id == run.id,
            Message.agent_message_id == agent_message_id,
            Message.role == "assistant",
        )
    )
    if entity is None:
        entity = Message(
            agent_message_id=agent_message_id,
            session_id=run.session_id,
            run_id=run.id,
            role="assistant",
            content=delta,
        )
        db.add(entity)
    else:
        entity.content += delta
    await db.flush()
    await append_event(
        db,
        run.id,
        "message_delta",
        {
            "run_id": run.id,
            "message_id": entity.id,
            "delta": delta,
        },
    )


async def process_agent_event(
    db: AsyncSession, run: Run, event_name: str, data: dict[str, Any]
) -> None:
    validate_agent_event(run, event_name, data)
    if event_name == "observability":
        return
    if event_name == "message_delta":
        await append_assistant_delta(db, run, data["message_id"], data["delta"])
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
                    "error": message("internal", run_locale(run)),
                },
            )
        # "ready" is deliberately ignored until the draft is validated and persisted.
    elif event_name == "plan":
        await persist_draft(db, run, data["plan"])
    elif event_name == "constraints_conflict":
        await save_assistant_message(db, run, message("constraints_conflict", run_locale(run)))
    elif event_name == "escalation":
        await save_assistant_message(db, run, message("escalation", run_locale(run)))
    elif event_name == "error":
        run.status = "error"
        candidate_code = data["error"]["code"]
        run.error_code = candidate_code if candidate_code in PUBLIC_ERROR_CODES else "internal"
        await append_event(
            db,
            run.id,
            "error",
            {
                "run_id": run.id,
                "error": {
                    "code": run.error_code,
                    "message": safe_message(run.error_code, run_locale(run)),
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
    locale = run_locale(run)
    error_message = safe_message(error.code, locale)
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
                    "error": error_message,
                },
            )
    await append_event(
        db,
        run.id,
        "error",
        {"run_id": run.id, "error": {"code": error.code, "message": error_message}},
    )
    await append_event(db, run.id, "run_status", {"run_id": run.id, "status": "error"})


async def build_agent_payload(
    run_id: str, default_locale: str
) -> tuple[dict[str, Any], str] | None:
    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        if run is None or run.status in TERMINAL_STATUSES:
            return None
        session = await db.get(ChatSession, run.session_id)
        payload = {
            "external_run_id": run.id,
            "correlation_id": run.correlation_id,
            "session_id": run.session_id,
            "user_id": run.user_id,
            "mode": run.mode,
            "locale": run.input_payload.get("locale", default_locale),
            **({"thread_id": session.thread_id} if session and session.thread_id else {}),
            **({"group_id": session.group_id} if session and session.group_id else {}),
            **({"active_plan_id": run.active_plan_id} if run.active_plan_id else {}),
        }
        if run.mode in {"new_trip", "qa"}:
            payload["message"] = run.input_payload["message"]
        elif run.mode == "answer":
            payload["answer"] = run.input_payload["answer"]
        elif run.mode == "modify":
            payload["route_edits"] = run.input_payload["route_edits"]
        return payload, run.correlation_id


async def save_agent_mapping(run_id: str, created: CreatedRun) -> bool:
    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        if run is None or run.status in TERMINAL_STATUSES:
            return False
        session = await db.get(ChatSession, run.session_id)
        run.agent_run_id = created.agent_run_id
        run.agent_thread_id = created.thread_id
        run.agent_stream_url = created.stream_url
        if session:
            session.thread_id = created.thread_id
        run.status = "running"
        await append_event(db, run.id, "run_status", {"run_id": run.id, "status": "running"})
        await db.commit()
        return True


async def process_persisted_agent_event(run_id: str, event_name: str, data: dict[str, Any]) -> bool:
    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        if run is None or run.status == "cancelled":
            return False
        await process_agent_event(db, run, event_name, data)
        await db.commit()
        return True


async def fail_persisted_run(run_id: str, error: APIError) -> None:
    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        if run is None or run.status == "cancelled":
            return
        await fail_run(db, run, error)
        await db.commit()


async def ensure_terminal_run(run_id: str) -> None:
    async with SessionFactory() as db:
        run = await db.get(Run, run_id)
        if run and run.status not in TERMINAL_STATUSES:
            await fail_run(db, run, APIError(502, "agent_unavailable"))
            await db.commit()


async def execute_run(run_id: str) -> None:
    settings = get_settings()
    client = AgentServiceClient(settings)
    try:
        prepared = await build_agent_payload(run_id, settings.default_locale)
        if prepared is None:
            return
        payload, correlation_id = prepared
        created = await client.create_run(payload, correlation_id)
        if not await save_agent_mapping(run_id, created):
            return
        async for event in client.stream(created.stream_url, correlation_id):
            if not await process_persisted_agent_event(run_id, event.event, event.data):
                return
        await ensure_terminal_run(run_id)
    except APIError as exc:
        await fail_persisted_run(run_id, exc)
    except Exception:
        await fail_persisted_run(run_id, APIError(500, "internal"))
    finally:
        await client.close()
