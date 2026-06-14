import asyncio
from uuid import uuid4

from conftest import register_user
from sqlalchemy import select

from travel_backend.database import SessionFactory
from travel_backend.models import ChatSession, Run, RunEvent, User
from travel_backend.services.runs import append_event


async def test_stream_ticket_and_persisted_sse_replay(client, unique_email):
    _, headers = await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="SSE test")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id=str(uuid4()),
            mode="qa",
            status="completed",
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.flush()
        await append_event(db, run.id, "run_status", {"run_id": run.id, "status": "started"})
        await append_event(db, run.id, "run_status", {"run_id": run.id, "status": "completed"})
        await db.commit()
        run_id = run.id

    ticket_response = await client.post(f"/api/v1/chat/{run_id}/stream-ticket", headers=headers)
    assert ticket_response.status_code == 200
    ticket = ticket_response.json()["ticket"]

    streamed = await client.get(f"/api/v1/chat/{run_id}/stream?ticket={ticket}")
    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert "event: run_status" in streamed.text
    assert '"status": "completed"' in streamed.text

    replay = await client.get(f"/api/v1/chat/{run_id}/stream?ticket={ticket}")
    assert replay.status_code == 401

    resumed = await client.get(
        f"/api/v1/chat/{run_id}/stream?ticket={ticket}",
        headers={"Last-Event-ID": "1"},
    )
    assert resumed.status_code == 200
    assert "id: 2" in resumed.text
    assert "id: 1" not in resumed.text

    invalid = await client.get(f"/api/v1/chat/{run_id}/stream?ticket=invalid")
    assert invalid.status_code == 401


async def test_run_event_sequences_are_atomic_under_concurrency(client, unique_email):
    await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Concurrent SSE")
        db.add(session)
        await db.flush()
        run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id=str(uuid4()),
            mode="qa",
            status="running",
            input_payload={"message": "test"},
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    async def writer(label: str) -> None:
        async with SessionFactory() as db:
            await append_event(db, run_id, "message", {"run_id": run_id, "label": label})
            await db.commit()

    await asyncio.gather(writer("first"), writer("second"))

    async with SessionFactory() as db:
        events = (
            await db.scalars(
                select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.sequence)
            )
        ).all()
        run = await db.get(Run, run_id)
    assert [event.sequence for event in events] == [1, 2]
    assert run.event_sequence == 2
