# Backend Implementation Notes

## Frozen-contract interpretations

- The frontend OpenAPI remains backward-compatible: the existing `MapPoint` schema gained only
  optional rich-content fields. No endpoint, required property, or SSE event name changed.
- The frontend stream ticket is single-use for its first connection. After consumption it remains
  valid only for reconnects to the same run during a five-minute lease, allowing browser
  `EventSource` reconnection with `Last-Event-ID`. First use is claimed by a conditional database
  update, so two concurrent initial requests cannot both succeed.
- Agent map points and calendar events do not contain IDs. The backend assigns UUIDs when a valid
  draft is persisted.
- Agent `plan_status=ready` is ignored until the accompanying draft has passed backend validation,
  offer hydration, cost recalculation, and persistence.
- Seed groups `G-0001` through `G-0006` are internal fixtures. They are available to the service
  token API and tests, but never returned by the public user group endpoints.
- The new implementation prompt permits globally visible seed groups but does not require them.
  The previously approved, stricter internal-only policy is retained to avoid exposing synthetic
  traveler profiles through user JWT endpoints.
- Inventory data has no availability dates, capacity, or layover duration. Search endpoints filter
  only fields represented by the dataset; unsupported validation inputs produce warnings.
- Package-tour cost is not double-counted: included flight/hotel components are not added again.
- Frontend OpenAPI paths are mounted under `/api/v1` because its `servers` entry and the global
  specification define that base path. Internal Contract B paths are mounted under `/internal`.
- `app/` contains only `__init__.py` and `main.py`, preserving the `app.main:app` ASGI command
  without maintaining duplicate re-export modules. Runtime logic lives in `src/travel_backend/`.
- Agent message IDs are untrusted correlation values. Persisted messages always receive a local
  UUID; `agent_message_id` is private storage metadata and is not part of the frontend contract.
  The first streamed delta creates the local message mapping, and its UUID is reused by later
  deltas and the final message event.
- Backend-only upstream failures (`timeout`, `agent_unavailable`) remain available in SSE run
  errors, while frontend HTTP responses normalize them to the frozen `internal` code. Persisted
  run and plan failure text uses the locale stored in the run payload.
- Backend-generated ready-plan summaries and messages also use the locale stored in the run.
  Agent-provided content is persisted without language rewriting.
- Stream tickets are checked against both the requested run and the run owner before first
  consumption; a mismatched stored owner cannot open or consume the ticket.
- Rich map fields are optional flat `MapPoint` properties for backward compatibility. Validated
  extensions are stored in `plan_map_points.details`; core coordinates and ordering remain normal
  columns. This avoids a wide MVP table while keeping one canonical serializer.
- `description` is accepted only as a compatibility alias of `summary`. The backend emits equal
  values for both when a summary exists and never synthesizes other place content.
- Agent `calendar_event_ref` and calendar `route_ref` are private draft correlation values. They
  are resolved to a backend-owned `calendar_event_id` and are not persisted as public metadata.
- Oversized or malformed rich content rejects the complete plan rather than being silently
  truncated. The backend validates structure and provenance markers but cannot establish factual
  correctness.
- Public map serialization uses an explicit allowlist of optional `MapPoint` properties. Unknown
  keys in a corrupted JSON details row are not returned, and HTML-like strings remain inert text.
- Agent SSE frames are limited to 1.1 MB, matching the draft-plan envelope with small protocol
  overhead. Agent message correlation IDs are limited to 200 characters. Clarifying questions and
  their options are normalized to the frozen public fields, dropping unknown Agent metadata.
- `route_preview` remains documentation-only until both frozen SSE contracts receive a separately
  approved event extension.

## Runtime

The target runtime is Python 3.13.7. Dependencies are managed only through `pyproject.toml` and
`uv sync`. SQLite is the MVP database; SQLAlchemy models and Alembic keep the persistence boundary
portable. Reference recommendation CSVs remain evaluation fixtures rather than production
selection logic.

Application startup assumes `uv run alembic upgrade head` has already completed. It does not call
`create_all`; that helper is reserved for isolated tests. Migration `20260614_0001` still uses
`Base.metadata.create_all` and therefore reflects current metadata on a fresh database. Later
migrations remain conditional so upgrades from older databases are safe. Rewriting migration 0001
is intentionally deferred beyond the MVP.

Migration `20260614_0005` adds and backfills a per-run event counter. Event sequence allocation,
refresh rotation, and first stream-ticket consumption use database-level conditional updates.
Cancellation performs the Agent HTTP request without a checked-out database connection, then
conditionally records the terminal event.

Credentialed CORS does not accept `*`; deployments must configure explicit trusted origins.
The test dependency group includes `pytest-xdist`, and each worker receives its own temporary
SQLite file. Per-test table reset and rate-limit reset keep order-independent runs reproducible.

## Remaining MVP limitations

- Service-to-service authentication uses static bearer tokens, not mTLS or scoped service JWTs.
- Rate limiting is process-local memory and is not coordinated across multiple backend workers.
- Stream reconnect uses a short lease after first consumption to support browser `EventSource`;
  it is single-use for an initial connection but intentionally reusable with `Last-Event-ID` during
  that lease.
- Agent calls have bounded connect/read timeouts and safe errors but no distributed circuit breaker
  or automatic retry policy.
- SQLite is suitable for the MVP and tests; production multi-worker deployment should use
  PostgreSQL and a distributed rate-limit/event notification layer.
- Rich route fields accepted by the backend are not yet typed in frozen Contract A. They remain
  forward-compatible JSON properties, but generated Agent Service clients need a future approved
  contract revision for first-class types.
- Seed reconciliation is transactional and repair-oriented but does not provide a distributed lock
  for concurrent startup across multiple production replicas.
- Inventory still lacks availability, capacity, and layover duration, so those checks can only
  produce warnings rather than hard filtering.
- Localization currently provides backend-owned messages for `ru-RU` and `en-US`; domain content
  from the synthetic dataset is not translated.
