# Agent Route Content Expectations

This document describes the structured route content expected from the future Agent Service. It is
an implementation hand-off, not a replacement for `agent-service/openapi.yaml`. The current
Contract A transports route points and calendar events inside the `plan` event's `DraftPlan`.
Separate Agent `map`, `calendar`, and `route_preview` events are not currently accepted.

## Ownership

The Agent Service owns place intelligence: summaries, history, facts, tips, food guidance,
practical notes, recommendation rationale, provenance, and confidence. The backend only validates,
persists, normalizes, and returns supplied content. It never invents missing semantic content.

User-facing content should be Russian by default. Field names, enum values, and source markers are
English. All strings are plain text, not HTML.

## Draft plan

`plan.selections` and `plan.map_points` remain required. A draft accepts at most 100 map points,
200 calendar events, 50 warnings, and 1 MB of validated JSON content. Point `order` values and
calendar `route_ref` values must be unique.

Each map point requires:

| Field | Type |
|---|---|
| `name` | non-empty string, max 200 |
| `kind` | `origin`, `destination`, or `stop` |
| `lat`, `lng` | valid coordinates |
| `order` | unique non-negative integer |

Food venues remain `kind=stop`; food specialization is expressed through optional content fields.

## Optional route fields

| Fields | Rules |
|---|---|
| `note` | max 2000 characters |
| `visit_date` | ISO date |
| `visit_time` | valid local `HH:MM` |
| `visit_start`, `visit_end` | RFC 3339 with timezone; end cannot precede start |
| `duration_minutes` | 0 to 10080 |
| `cost_rub`, `average_check_rub` | non-negative integer rubles |
| `price_note` | max 1000 characters |
| `ref_id` | optional public business reference, max 200 |
| `transport_to_next` | max 1000 characters |
| `travel_time_to_next_minutes` | 0 to 10080 |
| `distance_to_next_km` | 0 to 50000 |

To link a point to a calendar event, place an opaque `route_ref` on the calendar event and the same
value in the point's `calendar_event_ref`. These are private correlation values. The backend
replaces them with its own public `calendar_event_id`; unresolved or duplicate references reject
the draft.

## Rich place content

| Field | Type and maximum |
|---|---|
| `summary` | string, 1000 |
| `description` | legacy alias of `summary`, 1000 |
| `historical_background` | string, 4000 |
| `interesting_facts` | up to 20 non-empty strings, 500 each |
| `visit_tips` | up to 20 non-empty strings, 500 each |
| `food_recommendations` | up to 20 non-empty strings, 500 each |
| `signature_dishes` | up to 20 non-empty strings, 500 each |
| `booking_advice` | string, 2000 |
| `accessibility_notes` | string, 2000 |
| `safety_notes` | string, 2000 |
| `weather_notes` | string, 2000 |
| `why_recommended` | string, 2000 |
| `content_source` | lowercase machine marker, max 100 |
| `content_confidence` | `low`, `medium`, or `high` |

Preferred source markers include `agent_generated`, `agent_rag`, `agent_external_tool`, and
`seed_data`. More specific lowercase markers may use digits, `_`, `:`, or `-`.

Use `summary` in new payloads. If only `description` is supplied, the backend promotes it to
`summary` and returns both aliases. If both are supplied they must match.

Unknown information must be omitted, not represented by guesses, empty claims, `"unknown"` prose,
or fabricated precision. Unknown fields are rejected. Invalid types and oversized values reject
the complete plan event with `validation_error`; the backend does not silently truncate factual
content.

## Content safety and provenance

- Do not claim a reservation, ticket purchase, opening time, price, accessibility feature, or
  booking confirmation unless the underlying tool or source supports it.
- Use `low` confidence when evidence is weak or indirect, and phrase the text accordingly.
- Historical facts, safety guidance, weather advice, and food recommendations must not be stated
  with unsafe certainty when provenance is weak.
- `agent_generated` indicates synthesis without a stronger retrieval/tool source. It is not proof
  of factual verification.
- Food fields should be omitted for non-food places unless they genuinely describe an adjacent
  food experience relevant to the stop.
- Never place raw HTML, executable content, credentials, internal prompts, or private Agent IDs in
  route content.

## Calendar events

Calendar events require `type`, `title`, and timezone-aware `start`. Optional `end` cannot precede
`start`; `location`, `ref_id`, `notes`, and private `route_ref` are bounded strings. The backend
assigns the public calendar event ID.

## Route preview

Do not emit `route_preview` under the current Contract A. A future contract revision may define
safe progress fields (`status`, basic origin/destination, points, line, message, progress, stage),
but it requires explicit backend and frontend event-schema approval first.

