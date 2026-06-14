from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TravelGroup(Base, TimestampMixin):
    __tablename__ = "travel_groups"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    name: Mapped[str] = mapped_column(String(200))
    comment: Mapped[str | None] = mapped_column(Text)
    budget_rub: Mapped[int | None] = mapped_column(Integer)
    origin_city: Mapped[str | None] = mapped_column(String(120))
    destination: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    members: Mapped[list[GroupMember]] = relationship(
        back_populates="group", cascade="all, delete-orphan", lazy="selectin"
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    external_id: Mapped[str | None] = mapped_column(String, index=True)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("travel_groups.id", ondelete="CASCADE"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(200))
    age: Mapped[int | None] = mapped_column(Integer)
    citizenship: Mapped[str | None] = mapped_column(String(20))
    home_airport: Mapped[str | None] = mapped_column(String(20))
    role_in_group: Mapped[str | None] = mapped_column(String(80))
    loyalty_program: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    group: Mapped[TravelGroup] = relationship(back_populates="members")
    preferences: Mapped[list[Preference]] = relationship(
        back_populates="member", cascade="all, delete-orphan", lazy="selectin"
    )


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    member_id: Mapped[str] = mapped_column(
        ForeignKey("group_members.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str | None] = mapped_column(String(100))
    value: Mapped[str | None] = mapped_column(String(300))
    comment: Mapped[str | None] = mapped_column(Text)
    member: Mapped[GroupMember] = relationship(back_populates="preferences")


class FlightOffer(Base):
    __tablename__ = "flight_offers"

    flight_id: Mapped[str] = mapped_column(String, primary_key=True)
    origin_city: Mapped[str] = mapped_column(String(120), index=True)
    destination: Mapped[str] = mapped_column(String(120), index=True)
    price_rub: Mapped[int] = mapped_column(Integer)
    baggage_included: Mapped[bool] = mapped_column(Boolean)
    stops: Mapped[int] = mapped_column(Integer)
    departure_time: Mapped[str] = mapped_column(String(5))
    arrival_time: Mapped[str] = mapped_column(String(5))
    fare_type: Mapped[str] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)


class HotelOffer(Base):
    __tablename__ = "hotel_offers"

    hotel_id: Mapped[str] = mapped_column(String, primary_key=True)
    destination: Mapped[str] = mapped_column(String(120), index=True)
    stars: Mapped[int] = mapped_column(Integer)
    price_per_night_rub: Mapped[int] = mapped_column(Integer)
    breakfast_included: Mapped[bool] = mapped_column(Boolean)
    free_cancellation: Mapped[bool] = mapped_column(Boolean)
    rating: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)


class TourOffer(Base):
    __tablename__ = "tour_offers"

    tour_id: Mapped[str] = mapped_column(String, primary_key=True)
    destination: Mapped[str] = mapped_column(String(120), index=True)
    total_price_rub: Mapped[int] = mapped_column(Integer)
    includes_flight: Mapped[bool] = mapped_column(Boolean)
    includes_transfer: Mapped[bool] = mapped_column(Boolean)
    hotel_id: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("travel_groups.id"))
    thread_id: Mapped[str | None] = mapped_column(String, unique=True)
    summary: Mapped[str] = mapped_column(String(300))


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("travel_groups.id"), index=True)
    active_plan_id: Mapped[str | None] = mapped_column(String)
    agent_run_id: Mapped[str | None] = mapped_column(String, unique=True)
    agent_thread_id: Mapped[str | None] = mapped_column(String, index=True)
    agent_stream_url: Mapped[str | None] = mapped_column(String)
    correlation_id: Mapped[str] = mapped_column(String, unique=True)
    mode: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="started")
    outcome: Mapped[str | None] = mapped_column(String(50))
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_name: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    question: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    answer: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    plan_ref: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[str | None] = mapped_column(ForeignKey("travel_groups.id"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="building")
    summary: Mapped[str | None] = mapped_column(Text)
    destination: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    decision_rationale: Mapped[str | None] = mapped_column(Text)
    estimated_total_rub: Mapped[int | None] = mapped_column(Integer)
    flight_id: Mapped[str | None] = mapped_column(ForeignKey("flight_offers.flight_id"))
    hotel_id: Mapped[str | None] = mapped_column(ForeignKey("hotel_offers.hotel_id"))
    tour_id: Mapped[str | None] = mapped_column(ForeignKey("tour_offers.tour_id"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)


class PlanMapPoint(Base):
    __tablename__ = "plan_map_points"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    order: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)


class PlanCalendarEvent(Base):
    __tablename__ = "plan_calendar_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(300))
    ref_id: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)


class StreamTicket(Base):
    __tablename__ = "stream_tickets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ticket_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
