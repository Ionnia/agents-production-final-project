from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import __version__
from .config import get_settings
from .runs import RunManager
from .schemas import (
    CancelResponse,
    CreateRunRequest,
    Health,
    RunCreated,
    RunStatus,
    ServiceInfo,
)
from .security import require_correlation_id, require_service_token


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.manager = RunManager(get_settings())
    yield


app = FastAPI(title="Agent Service API (Contract A)", version=__version__, lifespan=lifespan)


def manager(request: Request) -> RunManager:
    return request.app.state.manager


@app.exception_handler(HTTPException)
async def _http_exc(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    code = {401: "unauthorized", 404: "not_found", 422: "validation_error"}.get(exc.status_code, "internal")
    return JSONResponse(
        status_code=exc.status_code, content={"error": {"code": code, "message": str(exc.detail)}}
    )


def _not_found() -> HTTPException:
    return HTTPException(404, detail={"error": {"code": "not_found", "message": "Unknown run/thread."}})


# ── Service ──────────────────────────────────────────────────────────────────────────────────
@app.get("/v1/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok")


@app.get("/v1/info", response_model=ServiceInfo, dependencies=[Depends(require_service_token)])
async def info(request: Request) -> ServiceInfo:
    settings = get_settings()
    planner_name = manager(request).planner_name
    return ServiceInfo(
        service="travel-agent-service",
        version=__version__,
        model=settings.gigachat_model,
        graph_version="final-v1",
        capabilities=["runs", "sse", "contract_b", f"planner:{planner_name}"],
    )


# ── Runs ─────────────────────────────────────────────────────────────────────────────────────
@app.post(
    "/v1/runs",
    response_model=RunCreated,
    status_code=202,
    dependencies=[Depends(require_service_token), Depends(require_correlation_id)],
)
async def create_run(req: CreateRunRequest, request: Request) -> RunCreated:
    run = await manager(request).start(req)
    return RunCreated(
        agent_run_id=run.agent_run_id,
        thread_id=run.thread_id,
        status="started",
        stream_url=f"/v1/runs/{run.agent_run_id}/stream",
    )


@app.get(
    "/v1/runs/{agent_run_id}/stream",
    dependencies=[Depends(require_service_token), Depends(require_correlation_id)],
)
async def stream_run(
    agent_run_id: str, request: Request, last_event_id: str | None = Header(default=None)
) -> StreamingResponse:
    run = manager(request).runs.get(agent_run_id)
    if run is None:
        raise _not_found()

    async def gen():
        async for event in manager(request).stream(run, last_event_id):
            yield f"id: {event.id}\nevent: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get(
    "/v1/runs/{agent_run_id}",
    response_model=RunStatus,
    dependencies=[Depends(require_service_token), Depends(require_correlation_id)],
)
async def get_run(agent_run_id: str, request: Request) -> RunStatus:
    run = manager(request).runs.get(agent_run_id)
    if run is None:
        raise _not_found()
    return RunStatus(
        agent_run_id=run.agent_run_id,
        thread_id=run.thread_id,
        status=run.status if run.status != "queued" else "queued",
        current_node=run.current_node,
        outcome=run.outcome,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
    )


@app.post(
    "/v1/runs/{agent_run_id}/cancel",
    dependencies=[Depends(require_service_token), Depends(require_correlation_id)],
)
async def cancel_run(agent_run_id: str, request: Request) -> JSONResponse:
    run = manager(request).runs.get(agent_run_id)
    if run is None:
        raise _not_found()
    if not await manager(request).request_cancel(run):
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "conflict", "message": "Run already finished."}},
        )
    return JSONResponse(
        status_code=202, content=CancelResponse(agent_run_id=agent_run_id, status="cancelling").model_dump()
    )


# ── Threads (debug/demo) ───────────────────────────────────────────────────────────────────────
@app.get(
    "/v1/threads/{thread_id}/state",
    dependencies=[Depends(require_service_token), Depends(require_correlation_id)],
)
async def thread_state(thread_id: str, request: Request) -> dict:
    thread = manager(request).threads.get(thread_id)
    if thread is None:
        raise _not_found()
    return {
        "thread_id": thread.thread_id,
        "session_id": thread.session_id,
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
        "messages": thread.messages,
        "state": thread.state,
    }
