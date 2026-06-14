#!/bin/sh
# Build the RAG policy index on first start (needs GigaChat creds), then serve.
# The index lives under the mounted /app/data volume, so it is built once.
set -e

INDEX_DIR=/app/data/indexes/policy_chroma
if [ ! -d "$INDEX_DIR" ] || [ -z "$(ls -A "$INDEX_DIR" 2>/dev/null)" ]; then
  echo "[agent] building RAG policy index (first run)…"
  python /app/agent/scripts/build_policy_index.py
else
  echo "[agent] RAG policy index present — skipping build."
fi

LEVEL="$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')"
echo "[agent] starting uvicorn on 0.0.0.0:8001 (log level ${LEVEL})"
exec uvicorn agent_service.main:app --host 0.0.0.0 --port 8001 --log-level "${LEVEL}"
