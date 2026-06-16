import json
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class RegisterRequest(APIModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(APIModel):
    refresh_token: str = Field(min_length=20, max_length=500)


class PreferenceInput(APIModel):
    type: str | None = None
    value: str | None = None
    comment: str | None = None


class MemoryPreferenceInput(PreferenceInput):
    traveler_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: str | None = Field(default=None, max_length=120)


class SaveMemoryPreferencesRequest(APIModel):
    preferences: list[MemoryPreferenceInput] = Field(default_factory=list, max_length=20)


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
        answer = self.in_reply_to_question_id and (self.selected_option_ids or self.freeform)
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


ContentConfidence = Literal["low", "medium", "high"]


class AgentMapPoint(APIModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["origin", "destination", "stop"]
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    order: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=1000)
    summary: str | None = Field(default=None, max_length=1000)
    visit_date: date | None = None
    visit_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    visit_start: datetime | None = None
    visit_end: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0, le=10080)
    cost_rub: int | None = Field(default=None, ge=0)
    price_note: str | None = Field(default=None, max_length=1000)
    calendar_event_ref: str | None = Field(default=None, min_length=1, max_length=200)
    ref_id: str | None = Field(default=None, max_length=200)
    transport_to_next: str | None = Field(default=None, max_length=1000)
    travel_time_to_next_minutes: int | None = Field(default=None, ge=0, le=10080)
    distance_to_next_km: float | None = Field(default=None, ge=0, le=50000)
    historical_background: str | None = Field(default=None, max_length=4000)
    interesting_facts: list[str] = Field(default_factory=list, max_length=20)
    visit_tips: list[str] = Field(default_factory=list, max_length=20)
    food_recommendations: list[str] = Field(default_factory=list, max_length=20)
    signature_dishes: list[str] = Field(default_factory=list, max_length=20)
    average_check_rub: int | None = Field(default=None, ge=0)
    booking_advice: str | None = Field(default=None, max_length=2000)
    accessibility_notes: str | None = Field(default=None, max_length=2000)
    safety_notes: str | None = Field(default=None, max_length=2000)
    weather_notes: str | None = Field(default=None, max_length=2000)
    why_recommended: str | None = Field(default=None, max_length=2000)
    content_source: str | None = Field(
        default=None,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_:-]*$",
    )
    content_confidence: ContentConfidence | None = None

    @field_validator(
        "interesting_facts",
        "visit_tips",
        "food_recommendations",
        "signature_dishes",
    )
    @classmethod
    def validate_short_items(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("list items must contain 1 to 500 characters")
        return value

    @field_validator("visit_time")
    @classmethod
    def validate_visit_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        hour, minute = (int(part) for part in value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("visit_time must be a valid HH:MM value")
        return value

    @field_validator("visit_start", "visit_end")
    @classmethod
    def require_visit_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("visit datetimes must include a timezone offset")
        return value

    @model_validator(mode="after")
    def normalize_description(self) -> "AgentMapPoint":
        if self.summary is not None and self.description is not None:
            if self.summary != self.description:
                raise ValueError("description and summary must match when both are provided")
        elif self.summary is None:
            self.summary = self.description
        self.description = self.summary
        if self.visit_start and self.visit_end and self.visit_end < self.visit_start:
            raise ValueError("visit_end must not be before visit_start")
        return self

    def public_details(self, calendar_event_id: str | None = None) -> dict[str, Any]:
        excluded = {"name", "kind", "lat", "lng", "order", "note", "calendar_event_ref"}
        details = self.model_dump(mode="json", exclude_none=True, exclude=excluded)
        if self.summary is not None:
            details["description"] = self.summary
        if calendar_event_id is not None:
            details["calendar_event_id"] = calendar_event_id
        return {key: value for key, value in details.items() if value != []}


class AgentCalendarEvent(APIModel):
    type: Literal["flight", "hotel", "tour", "activity"]
    title: str = Field(min_length=1, max_length=300)
    start: datetime
    end: datetime | None = None
    location: str | None = Field(default=None, max_length=300)
    ref_id: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    route_ref: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("start", "end")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("calendar datetimes must include a timezone offset")
        return value

    @model_validator(mode="after")
    def valid_interval(self) -> "AgentCalendarEvent":
        if self.end and self.end < self.start:
            raise ValueError("end must not be before start")
        return self


class AgentDraftPlan(APIModel):
    destination: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    selections: PlanSelectionForValidation
    estimated_total_rub: int | None = Field(default=None, ge=0)
    decision_rationale: str | None = Field(default=None, max_length=10000)
    map_points: list[AgentMapPoint] = Field(max_length=100)
    calendar_events: list[AgentCalendarEvent] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("warnings")
    @classmethod
    def validate_warnings(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("warnings must contain 1 to 500 characters")
        return value

    @model_validator(mode="after")
    def validate_route(self) -> "AgentDraftPlan":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        orders = [point.order for point in self.map_points]
        if len(orders) != len(set(orders)):
            raise ValueError("map point order values must be unique")
        route_refs = [event.route_ref for event in self.calendar_events if event.route_ref]
        if len(route_refs) != len(set(route_refs)):
            raise ValueError("calendar route_ref values must be unique")
        payload_size = len(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")
        )
        if payload_size > 1_000_000:
            raise ValueError("agent plan payload must not exceed 1 MB")
        return self


class AgentEvent(APIModel):
    event: str
    data: dict[str, Any]
    id: str | None = None


class HealthResponse(APIModel):
    status: Literal["ok", "degraded"]
    detail: str | None = None
