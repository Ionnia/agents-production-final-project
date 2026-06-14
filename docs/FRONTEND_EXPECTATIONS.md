# Frontend Expectations for Route Maps

This document defines the expected future frontend behavior for route maps and place cards. It does
not prescribe a map provider or UI library and does not change the current frontend implementation.
The authoritative wire contract remains `api/openapi.yaml`.

## Data flow

1. Start a run with `POST /api/v1/chat` or `POST /api/v1/plans/{plan_id}/modify`.
2. Mint a stream ticket and consume `GET /api/v1/chat/{run_id}/stream`.
3. Listen to the current SSE vocabulary:
   - `run_status`: run lifecycle and terminal closure.
   - `plan_status`: `building`, `ready`, or `error`.
   - `message_delta` and `message`: assistant text.
   - `clarifying_question`: user input required before planning can continue.
   - `map`: complete ordered map snapshot after backend validation.
   - `error`: run-level failure.
4. When `plan_status=ready`, use the latest `map` snapshot or fetch
   `GET /api/v1/plans/{plan_id}/map`. Fetch calendar data from
   `GET /api/v1/plans/{plan_id}/calendar`.

There is no `calendar` SSE event in the current contract. There is also no runtime
`route_preview` event yet. Both must be treated as absent rather than inferred from undocumented
events.

## Route rendering

- Sort points by `order`; do not rely on array arrival order.
- Draw the route line between the ordered coordinates. The backend does not calculate road
  geometry, navigation paths, or polylines.
- Use backend `id` values for selection and editing. Never use Agent Service internal IDs.
- `calendar_event_id`, when present, links a point to an event returned by the plan calendar
  endpoint.
- Treat `ref_id` as an optional public business reference, not as a DOM key or map-point identity.
- While the plan is not `ready`, the map is read-only. The `/map` response also exposes `editable`.

## Place cards

The required route fields are `id`, `name`, `kind`, `lat`, `lng`, and `order`. Every other field is
optional. A card may display:

- visit timing: `visit_date`, `visit_time`, `visit_start`, `visit_end`, `duration_minutes`;
- cost: `cost_rub`, `price_note`, `average_check_rub`;
- overview: `summary`, with deprecated `description` as an equivalent fallback;
- context: `historical_background`, `interesting_facts`, `visit_tips`;
- food details: `food_recommendations`, `signature_dishes`;
- practical guidance: `booking_advice`, `accessibility_notes`, `safety_notes`, `weather_notes`;
- recommendation rationale: `why_recommended`;
- onward travel: `transport_to_next`, `travel_time_to_next_minutes`,
  `distance_to_next_km`;
- provenance: `content_source`, `content_confidence`.

Food fields may be absent for any point and should normally be shown only for a food-related stop.
Missing fields must collapse cleanly without empty headings, placeholder facts, or invented values.
The frontend should prefer `summary`; use `description` only as a legacy fallback.

All Agent-provided content is untrusted plain text. Render strings as text, never as raw HTML.
URLs, markup, scripts, and booking claims inside strings have no privileged meaning.

## Loading and motion

- `run_status=started|running` and `plan_status=building` are the supported route-building signals.
- A future frontend may show an old-adventure-map style progress treatment while these states are
  active, but it must not imply that actual route coordinates are available before a `map` event.
- Respect the user's reduced-motion preference. Replace path-drawing, camera movement, and animated
  markers with static state transitions when reduced motion is enabled.
- Use Russian labels and fallback copy by default. API field names and enum values remain English.

## Reserved route preview

`route_preview` is a future optional capability, not part of the current SSE contract. If it is
introduced through a separately approved contract revision, the intended payload is:

```json
{
  "run_id": "backend-run-id",
  "status": "building",
  "origin": "Moscow",
  "destination": "Istanbul",
  "points": [],
  "line": [],
  "message": "Строим маршрут",
  "progress": 0.4,
  "stage": "searching"
}
```

Allowed statuses would be `building`, `searching`, `validating`, `ready`, and `failed`. Until that
revision exists, clients must not listen for or depend on this event.

