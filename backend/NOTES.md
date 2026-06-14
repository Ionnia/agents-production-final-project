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
- Inventory data has no availability dates, capacity, or layover duration. Search endpoints filter
  only fields represented by the dataset; unsupported validation inputs produce warnings.
- Package-tour cost is not double-counted: included flight/hotel components are not added again.

## Runtime

The target runtime is Python 3.13.7. Dependencies are managed only through `pyproject.toml` and
`uv sync`. SQLite is the MVP database; SQLAlchemy models and Alembic keep the persistence boundary
portable.
