import asyncio
import json
from datetime import UTC, timedelta
from secrets import token_urlsafe
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from ..clients.agent_service import AgentServiceClient
from ..config import get_settings
from ..database import SessionFactory
from ..errors import APIError
from ..i18n import choose_locale
from ..models import (
    ChatSession,
    Message,
    Plan,
    Run,
    RunEvent,
    StreamTicket,
    TravelGroup,
    utcnow,
)
from ..rate_limit import check_rate_limit
from ..schemas import ChatRequest, ModifyRequest
from ..security import CurrentUser, Database, hash_token
from ..services.runs import TERMINAL_STATUSES, append_event, execute_run

router = APIRouter(tags=["Chat"])


async def owned_run(db: Database, user_id: str, run_id: str) -> Run:
    run = await db.scalar(select(Run).where(Run.id == run_id, Run.user_id == user_id))
    if run is None:
        raise APIError(404, "not_found")
    return run


async def validate_user_group(db: Database, user_id: str, group_id: str) -> TravelGroup:
    group = await db.scalar(
        select(TravelGroup).where(
            TravelGroup.id == group_id,
            TravelGroup.owner_id == user_id,
            TravelGroup.is_internal.is_(False),
        )
    )
    if group is None:
        raise APIError(404, "not_found")
    return group


@router.post("/chat", status_code=202)
async def post_chat(
    body: ChatRequest,
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser,
    db: Database,
) -> dict:
    check_rate_limit(f"chat:{user.id}")
    settings = get_settings()
    locale = choose_locale(
        request.headers.get("accept-language"),
        settings.supported_locales,
        settings.default_locale,
    )
    if body.group_id:
        await validate_user_group(db, user.id, body.group_id)
    if body.session_id:
        session = await db.scalar(
            select(ChatSession).where(
                ChatSession.id == body.session_id, ChatSession.user_id == user.id
            )
        )
        if session is None:
            raise APIError(404, "not_found")
        if body.group_id:
            session.group_id = body.group_id
    else:
        summary_source = body.message or body.freeform or "Ответ на уточняющий вопрос"
        session = ChatSession(
            user_id=user.id,
            group_id=body.group_id,
            summary=summary_source.strip()[:300],
        )
        db.add(session)
        await db.flush()

    if body.message:
        mode = "new_trip"
        payload = {"message": body.message, "locale": locale}
        content = body.message
        answer = None
    else:
        mode = "answer"
        answer = {
            "in_reply_to_question_id": body.in_reply_to_question_id,
            **(
                {"selected_option_ids": body.selected_option_ids}
                if body.selected_option_ids
                else {}
            ),
            **({"freeform": body.freeform} if body.freeform else {}),
        }
        payload = {"answer": answer, "locale": locale}
        content = body.freeform or ", ".join(body.selected_option_ids or [])

    run = Run(
        session_id=session.id,
        user_id=user.id,
        correlation_id=str(uuid4()),
        mode=mode,
        input_payload=payload,
        status="started",
    )
    db.add(run)
    await db.flush()
    db.add(
        Message(
            session_id=session.id,
            run_id=run.id,
            role="user",
            content=content,
            answer=answer,
        )
    )
    await append_event(
        db, run.id, "run_status", {"run_id": run.id, "status": "started"}
    )
    await db.commit()
    background.add_task(execute_run, run.id)
    return {"run_id": run.id, "session_id": session.id}


@router.post("/chat/{run_id}/stream-ticket")
async def create_stream_ticket(run_id: str, user: CurrentUser, db: Database) -> dict:
    await owned_run(db, user.id, run_id)
    settings = get_settings()
    raw = token_urlsafe(32)
    db.add(
        StreamTicket(
            run_id=run_id,
            user_id=user.id,
            ticket_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(seconds=settings.stream_ticket_ttl_seconds),
        )
    )
    await db.commit()
    return {"ticket": raw, "expires_in": settings.stream_ticket_ttl_seconds}


@router.get("/chat/{run_id}/stream")
async def stream_run(
    run_id: str,
    ticket: str = Query(...),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    settings = get_settings()
    async with SessionFactory() as db:
        entity = await db.scalar(
            select(StreamTicket).where(
                StreamTicket.ticket_hash == hash_token(ticket),
                StreamTicket.run_id == run_id,
            )
        )
        if entity is None:
            raise APIError(401, "unauthorized")
        now = utcnow()
        expires_at = entity.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        lease = entity.lease_expires_at
        if lease is not None and lease.tzinfo is None:
            lease = lease.replace(tzinfo=UTC)
        if entity.consumed_at is None:
            if expires_at <= now:
                raise APIError(401, "unauthorized")
            entity.consumed_at = now
            entity.lease_expires_at = now + timedelta(
                seconds=settings.stream_reconnect_lease_seconds
            )
            await db.commit()
        elif lease is None or lease <= now or not last_event_id:
            raise APIError(401, "unauthorized")

    try:
        start_sequence = int(last_event_id or 0)
    except ValueError as exc:
        raise APIError(422, "validation_error") from exc

    async def generator():
        sequence = start_sequence
        while True:
            async with SessionFactory() as db:
                events = (
                    await db.scalars(
                        select(RunEvent)
                        .where(
                            RunEvent.run_id == run_id,
                            RunEvent.sequence > sequence,
                        )
                        .order_by(RunEvent.sequence)
                    )
                ).all()
                for event in events:
                    sequence = event.sequence
                    yield ServerSentEvent(
                        data=json.dumps(event.payload, ensure_ascii=False),
                        event=event.event_name,
                        id=str(event.sequence),
                    )
                run = await db.get(Run, run_id)
                if run is None:
                    return
                if run.status in TERMINAL_STATUSES and not events:
                    return
            await asyncio.sleep(settings.sse_poll_interval_seconds)

    return EventSourceResponse(generator(), ping=15)


@router.post("/chat/{run_id}/cancel", status_code=202)
async def cancel_run(run_id: str, user: CurrentUser, db: Database) -> dict:
    run = await owned_run(db, user.id, run_id)
    if run.status in TERMINAL_STATUSES:
        raise APIError(409, "conflict")
    if run.agent_run_id:
        client = AgentServiceClient(get_settings())
        try:
            await client.cancel(run.agent_run_id, run.correlation_id)
        finally:
            await client.close()
    run.status = "cancelled"
    run.finished_at = utcnow()
    await append_event(
        db, run.id, "run_status", {"run_id": run.id, "status": "cancelled"}
    )
    await db.commit()
    return {"run_id": run.id, "status": "cancelling"}


@router.post("/plans/{plan_id}/modify", status_code=202)
async def modify_plan(
    plan_id: str,
    body: ModifyRequest,
    request: Request,
    background: BackgroundTasks,
    user: CurrentUser,
    db: Database,
) -> dict:
    check_rate_limit(f"modify:{user.id}")
    plan = await db.scalar(
        select(Plan).where(Plan.id == plan_id, Plan.user_id == user.id)
    )
    if plan is None:
        raise APIError(404, "not_found")
    if plan.status != "ready":
        raise APIError(409, "plan_not_ready")
    settings = get_settings()
    locale = choose_locale(
        request.headers.get("accept-language"),
        settings.supported_locales,
        settings.default_locale,
    )
    route_edits = body.model_dump(exclude_none=True)
    run = Run(
        session_id=plan.session_id,
        user_id=user.id,
        active_plan_id=plan.id,
        correlation_id=str(uuid4()),
        mode="modify",
        input_payload={"route_edits": route_edits, "locale": locale},
        status="started",
    )
    db.add(run)
    await db.flush()
    plan.status = "building"
    plan.run_id = run.id
    await append_event(
        db, run.id, "run_status", {"run_id": run.id, "status": "started"}
    )
    await append_event(
        db,
        run.id,
        "plan_status",
        {"run_id": run.id, "plan_id": plan.id, "status": "building"},
    )
    await db.commit()
    background.add_task(execute_run, run.id)
    return {"run_id": run.id}
