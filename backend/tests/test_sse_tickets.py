from datetime import timedelta
from uuid import uuid4

from conftest import register_user
from sqlalchemy import select

from travel_backend.database import SessionFactory
from travel_backend.models import ChatSession, Run, StreamTicket, User, utcnow


async def test_stream_ticket_is_hashed_scoped_and_expires(client, unique_email):
    _, headers = await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="Ticket test")
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
        other_run = Run(
            session_id=session.id,
            user_id=user.id,
            correlation_id=str(uuid4()),
            mode="qa",
            status="completed",
            input_payload={"message": "test"},
        )
        db.add_all([run, other_run])
        await db.commit()
        run_id = run.id
        other_run_id = other_run.id

    response = await client.post(
        f"/api/v1/chat/{run_id}/stream-ticket",
        headers=headers,
    )
    raw_ticket = response.json()["ticket"]
    async with SessionFactory() as db:
        ticket = await db.scalar(select(StreamTicket).where(StreamTicket.run_id == run_id))
        assert ticket.ticket_hash != raw_ticket
        ticket.expires_at = utcnow() - timedelta(seconds=1)
        await db.commit()

    expired = await client.get(f"/api/v1/chat/{run_id}/stream?ticket={raw_ticket}")
    assert expired.status_code == 401
    wrong_run = await client.get(f"/api/v1/chat/{other_run_id}/stream?ticket={raw_ticket}")
    assert wrong_run.status_code == 401


async def test_stream_rejects_access_jwt_as_query_ticket(client, unique_email):
    registered, headers = await register_user(client, unique_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        session = ChatSession(user_id=user.id, summary="JWT rejection")
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
        await db.commit()
        run_id = run.id
    access_token = registered["tokens"]["access_token"]
    response = await client.get(f"/api/v1/chat/{run_id}/stream?ticket={access_token}")
    assert response.status_code == 401
    assert headers["Authorization"].endswith(access_token)


async def test_stream_ticket_owner_must_match_run_owner(client, unique_email):
    _, headers = await register_user(client, unique_email)
    other_email = f"other-{unique_email}"
    await register_user(client, other_email)
    async with SessionFactory() as db:
        user = await db.scalar(select(User).where(User.email == unique_email))
        other_user = await db.scalar(select(User).where(User.email == other_email))
        session = ChatSession(user_id=user.id, summary="Ticket owner mismatch")
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
        await db.commit()
        run_id = run.id

    response = await client.post(
        f"/api/v1/chat/{run_id}/stream-ticket",
        headers=headers,
    )
    raw_ticket = response.json()["ticket"]
    async with SessionFactory() as db:
        ticket = await db.scalar(select(StreamTicket).where(StreamTicket.run_id == run_id))
        ticket.user_id = other_user.id
        await db.commit()
        ticket_id = ticket.id

    streamed = await client.get(f"/api/v1/chat/{run_id}/stream?ticket={raw_ticket}")
    assert streamed.status_code == 401
    assert streamed.json()["error"]["code"] == "unauthorized"
    async with SessionFactory() as db:
        ticket = await db.get(StreamTicket, ticket_id)
        assert ticket.consumed_at is None
        assert ticket.lease_expires_at is None
