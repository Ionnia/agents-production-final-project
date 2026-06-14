# Running with Docker Compose

The whole stack runs as three containers wired together by `docker-compose.yml`:

| Service | Image | Port (host) | Role |
|---|---|---|---|
| `frontend` | nginx serving the built Vite SPA | **5173** → 80 | UI; reverse-proxies `/api` → backend (same-origin, no CORS) |
| `backend` | FastAPI BFF | **8000** | API, auth, persistence, SSE; drives the agent |
| `agent-service` | FastAPI + LangGraph (+ `agent/` runtime) | _internal only_ | Contract A runs/SSE; calls GigaChat and Contract B |

```
browser → frontend:5173 (nginx) ──/api──▶ backend:8000 ──Contract A──▶ agent-service:8001
                                              ▲                              │
                                              └──────── Contract B ──────────┘  ──▶ GigaChat
```

## Quick start

```bash
cp .env.example .env          # then edit .env (see below)
docker compose up --build     # add -d to run detached
# open http://localhost:5173
```

`.env` (gitignored) must contain real values for:

- `GIGACHAT_CREDENTIALS` — the GigaChat Authorization key (scope `GIGACHAT_API_PERS`).
- `AGENT_SERVICE_TOKEN` and `BACKEND_TOOL_TOKEN` — two shared bearer tokens (any long random
  strings); compose injects the same value into both services.
- `JWT_SECRET` — random secret for signing user JWTs.

Compose reads `.env` automatically for `${VAR}` substitution; missing required vars fail fast with a
clear message.

## What happens on `up`

1. **backend** runs `alembic upgrade head`, then serves on `:8000` and seeds synthetic inventory +
   scenario groups from the mounted `./data` on startup. The SQLite DB lives in the named volume
   `backend-db` (survives restarts).
2. **agent-service** waits for the backend to be healthy, builds the RAG policy index into
   `./data/indexes/policy_chroma` **if missing** (first run only; needs GigaChat), then serves on
   `:8001` (internal).
3. **frontend** nginx serves the SPA on `:5173` and proxies `/api/*` (including the SSE stream) to
   `backend:8000`.

First `up` is slower: the agent image is large and the RAG index build calls GigaChat embeddings.
Subsequent runs reuse the cached image, the named DB volume, and the on-disk index.

## Useful commands

```bash
docker compose up --build -d        # start detached
docker compose ps                   # status + health
docker compose logs -f agent-service
docker compose down                 # stop (keeps volumes)
docker compose down -v              # stop and wipe DB volume (re-seeds next up)
docker compose build --no-cache agent-service   # force rebuild one service

# Health
curl http://localhost:8000/health           # backend -> 200
curl http://localhost:5173/api/v1/...        # through the nginx proxy
```

## Notes

- The agent-service port is **not** published to the host — only the backend talks to it, over the
  compose network. Publish it (add `ports: ["8001:8001"]`) only for debugging.
- `./data` is mounted read-only into the backend (seed CSVs) and read-write into the agent
  (writes the RAG index). The index is gitignored and persists on the host.
- To rebuild the RAG index, delete `data/indexes/policy_chroma` and restart the agent service.
- For a non-Docker local run, see [`LOCAL_E2E.md`](./LOCAL_E2E.md).
