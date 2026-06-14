from fastapi import APIRouter, Query
from sqlalchemy import func, select

from ..errors import APIError
from ..models import ChatSession, Message, Plan
from ..security import CurrentUser, Database
from ..services.serializers import (
    iso,
    plan_summary_dict,
    session_summary_dict,
)

router = APIRouter(prefix="/sessions", tags=["Sessions"])


async def owned_session(db: Database, user_id: str, session_id: str) -> ChatSession:
    session = await db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    if session is None:
        raise APIError(404, "not_found")
    return session


@router.get("")
async def list_sessions(
    user: CurrentUser,
    db: Database,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    total = await db.scalar(
        select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user.id)
    )
    sessions = (
        await db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    items = []
    for session in sessions:
        last_message = await db.scalar(
            select(Message)
            .where(Message.session_id == session.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        latest_plan = await db.scalar(
            select(Plan)
            .where(Plan.session_id == session.id)
            .order_by(Plan.created_at.desc())
            .limit(1)
        )
        preview = last_message.content[:160] if last_message else None
        items.append(session_summary_dict(session, preview, latest_plan))
    return {"items": items, "total": total or 0, "limit": limit, "offset": offset}


@router.get("/{session_id}")
async def get_session(session_id: str, user: CurrentUser, db: Database) -> dict:
    session = await owned_session(db, user.id, session_id)
    messages = (
        await db.scalars(
            select(Message)
            .where(Message.session_id == session.id)
            .order_by(Message.created_at, Message.id)
        )
    ).all()
    plans = (
        await db.scalars(
            select(Plan).where(Plan.session_id == session.id).order_by(Plan.created_at)
        )
    ).all()
    return {
        "id": session.id,
        "summary": session.summary,
        "created_at": iso(session.created_at),
        "updated_at": iso(session.updated_at),
        **({"group_id": session.group_id} if session.group_id else {}),
        "messages": [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "created_at": iso(item.created_at),
                **({"run_id": item.run_id} if item.run_id else {}),
                **({"question": item.question} if item.question else {}),
                **({"answer": item.answer} if item.answer else {}),
                **({"plan_ref": item.plan_ref} if item.plan_ref else {}),
            }
            for item in messages
        ],
        "plans": [await plan_summary_dict(db, item) for item in plans],
    }
