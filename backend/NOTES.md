# Backend Implementation Notes

## Frozen-contract interpretations

- The status text in the frozen `api/SPECIFICATION.md` still says the contract is not implemented.
  Per the task constraint, that frozen module was not edited; the root and backend specifications
  record the current implementation status.
- The frontend stream ticket is single-use for its first connection. After consumption it remains
  valid only for reconnects to the same run during a five-minute lease, allowing browser
  `EventSource` reconnection with `Last-Event-ID`.
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
- Backend-only upstream failures (`timeout`, `agent_unavailable`) remain available in SSE run
  errors, while frontend HTTP responses normalize them to the frozen `internal` code.

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
- Seed reconciliation is transactional and repair-oriented but does not provide a distributed lock
  for concurrent startup across multiple production replicas.
- Inventory still lacks availability, capacity, and layover duration, so those checks can only
  produce warnings rather than hard filtering.
- Localization currently provides backend-owned messages for `ru-RU` and `en-US`; domain content
  from the synthetic dataset is not translated.
