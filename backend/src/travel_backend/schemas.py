from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class RegisterRequest(APIModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(APIModel):
    email: EmailStr
    password: str


class RefreshRequest(APIModel):
    refresh_token: str = Field(min_length=20)


class PreferenceInput(APIModel):
    type: str | None = None
    value: str | None = None
    comment: str | None = None


class MemberInput(APIModel):
    full_name: str = Field(min_length=1, max_length=200)
    age: int | None = Field(default=None, ge=0, le=130)
    citizenship: str | None = None
    home_airport: str | None = None
    role_in_group: str | None = None
    loyalty_program: str | None = None
    notes: str | None = None
    preferences: list[PreferenceInput] = Field(default_factory=list)


class CreateGroupRequest(APIModel):
    name: str = Field(min_length=1, max_length=200)
    comment: str | None = None
    budget_rub: int | None = Field(default=None, ge=0)
    origin_city: str | None = None
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    members: list[MemberInput] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_dates(self) -> "CreateGroupRequest":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class ChatRequest(APIModel):
    session_id: str | None = None
    message: str | None = Field(default=None, min_length=1, max_length=10000)
    group_id: str | None = None
    in_reply_to_question_id: str | None = None
    selected_option_ids: list[str] | None = None
    freeform: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def one_input_mode(self) -> "ChatRequest":
        answer = self.in_reply_to_question_id and (
            self.selected_option_ids or self.freeform
        )
        if bool(self.message) == bool(answer):
            raise ValueError("provide message or a clarifying-question answer")
        return self


class AddPoint(APIModel):
    name: str = Field(min_length=1)
    kind: Literal["origin", "destination", "stop"] | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    after_point_id: str | None = None


class ModifyRequest(APIModel):
    add: list[AddPoint] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def non_empty(self) -> "ModifyRequest":
        if not self.add and not self.remove and not self.note:
            raise ValueError("at least one route edit or note is required")
        return self


class RejectRequest(APIModel):
    reason: str | None = Field(default=None, max_length=5000)


class FlightSearchRequest(APIModel):
    origin: str
    destination: str
    start_date: date | None = None
    end_date: date | None = None
    passengers_count: int | None = Field(default=None, ge=1)
    required_baggage: bool | None = None
    max_stops: int | None = Field(default=None, ge=0)
    avoid_night_arrival: bool | None = None
    budget_rub: int | None = Field(default=None, ge=0)


class HotelSearchRequest(APIModel):
    destination: str
    start_date: date | None = None
    end_date: date | None = None
    nights: int | None = Field(default=None, ge=1)
    guests_count: int | None = Field(default=None, ge=1)
    breakfast_required: bool | None = None
    free_cancellation_preferred: bool | None = None
    min_stars: int | None = Field(default=None, ge=1, le=5)
    budget_per_night_rub: int | None = Field(default=None, ge=0)


class TourSearchRequest(APIModel):
    destination: str
    start_date: date | None = None
    end_date: date | None = None
    pax: int | None = Field(default=None, ge=1)
    budget_rub: int | None = Field(default=None, ge=0)
    includes_flight: bool | None = None
    includes_transfer: bool | None = None


class PlanSelectionForValidation(APIModel):
    flight_id: str | None = None
    hotel_id: str | None = None
    tour_id: str | None = None
    total_cost_rub: int | None = Field(default=None, ge=0)


class ValidatePlanRequest(APIModel):
    group_id: str
    plan: PlanSelectionForValidation
    constraints: dict[str, Any] = Field(default_factory=dict)


class AgentDraftPlan(APIModel):
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    selections: PlanSelectionForValidation
    estimated_total_rub: int | None = None
    decision_rationale: str | None = None
    map_points: list[dict[str, Any]]
    calendar_events: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AgentEvent(APIModel):
    event: str
    data: dict[str, Any]
    id: str | None = None


class HealthResponse(APIModel):
    status: Literal["ok", "degraded"]
    detail: str | None = None

