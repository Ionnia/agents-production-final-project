#!/bin/sh
# Apply DB migrations (idempotent), then serve. Seeding happens on app startup.
set -e

mkdir -p /app/var

echo "[backend] alembic upgrade head…"
alembic upgrade head

LEVEL="$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')"
echo "[backend] starting uvicorn on 0.0.0.0:8000 (log level ${LEVEL})"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level "${LEVEL}"
