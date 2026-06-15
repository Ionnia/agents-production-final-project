from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .config import Settings
from .contract_b import ContractBClient, ContractBError
from .events import events_for
from .planner import Planner, user_text
from .schemas import CreateRunRequest

TERMINAL = {"completed", "cancelled", "error"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class StoredEvent:
    id: str
    event: str
    data: dict[str, Any]


@dataclass
class ThreadState:
    thread_id: str
    session_id: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    messages: list[dict[str, Any]] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class Run:
    agent_run_id: str
    thread_id: str
    external_run_id: str
    session_id: str
    status: str = "queued"
    outcome: str | None = None
    current_node: str | None = None
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None
    error: dict[str, str] | None = None
    events: list[StoredEvent] = field(default_factory=list)
    cancelled: bool = False
    _seq: int = 0
    _cond: asyncio.Condition = field(default_factory=asyncio.Condition)

    @property
    def done(self) -> bool:
        return self.status in TERMINAL


class RunManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._contract_b = ContractBClient(settings)
        self._planner = Planner(settings, self._contract_b)
        self.runs: dict[str, Run] = {}
        self.threads: dict[str, ThreadState] = {}
        # Strong references to in-flight executor tasks; the event loop only keeps a weak ref,
        # so without this the task could be GC'd mid-run and silently abort the stream.
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def planner_name(self) -> str:
        return self._planner.active_planner

    # ── lifecycle ────────────────────────────────────────────────────────────────────────────
    async def start(self, req: CreateRunRequest) -> Run:
        thread_id = req.thread_id or f"thr_{uuid.uuid4().hex}"
        thread = self.threads.setdefault(thread_id, ThreadState(thread_id=thread_id, session_id=req.session_id))
        thread.session_id = req.session_id
        run = Run(
            agent_run_id=f"ar_{uuid.uuid4().hex}",
            thread_id=thread_id,
            external_run_id=req.external_run_id,
            session_id=req.session_id,
        )
        self.runs[run.agent_run_id] = run
        task = asyncio.create_task(self._execute(run, req, thread))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return run

    async def _emit(self, run: Run, event: str, data: dict[str, Any]) -> None:
        async with run._cond:
            run._seq += 1
            run.events.append(StoredEvent(id=str(run._seq), event=event, data=data))
            if event == "run_status":
                status = data.get("status")
                if status in TERMINAL or status == "running":
                    run.status = status
                    run.outcome = data.get("outcome", run.outcome)
                    if status in TERMINAL:
                        run.finished_at = _now()
            run._cond.notify_all()

    async def _execute(self, run: Run, req: CreateRunRequest, thread: ThreadState) -> None:
        try:
            await self._emit(run, "run_status", {"agent_run_id": run.agent_run_id, "status": "running"})
            # Record the user turn for EVERY mode (message / answer / modify), not just
            # `new_trip`, so the thread carries the full dialogue into the next run — otherwise
            # clarifying answers were dropped from memory and the agent re-asked.
            turn = user_text(req)
            if turn:
                thread.messages.append({"role": "user", "content": turn, "created_at": _now()})

            result = await self._planner.plan(req, thread)
            thread.state["last_outcome"] = result.outcome_type
            thread.messages.append({"role": "assistant", "content": result.message, "created_at": _now()})
            thread.updated_at = _now()

            for event, data in events_for(result, run.agent_run_id):
                if run.cancelled:
                    await self._cancel(run)
                    return
                await self._emit(run, event, data)
        except ContractBError as exc:
            await self._fail(run, "agent_unavailable", str(exc))
        except Exception as exc:  # noqa: BLE001 — any planner/LLM failure becomes a stream error
            await self._fail(run, "internal", str(exc))

    async def _fail(self, run: Run, code: str, message: str) -> None:
        await self._emit(
            run, "error", {"agent_run_id": run.agent_run_id, "error": {"code": code, "message": message}}
        )
        run.error = {"code": code, "message": message}
        await self._emit(run, "run_status", {"agent_run_id": run.agent_run_id, "status": "error"})

    async def _cancel(self, run: Run) -> None:
        await self._emit(run, "run_status", {"agent_run_id": run.agent_run_id, "status": "cancelled"})

    async def request_cancel(self, run: Run) -> bool:
        if run.done:
            return False
        run.cancelled = True
        return True

    # ── SSE streaming with Last-Event-ID resume ─────────────────────────────────────────────
    async def stream(self, run: Run, last_event_id: str | None) -> AsyncIterator[StoredEvent]:
        last_seq = 0
        if last_event_id and last_event_id.isdigit():
            last_seq = int(last_event_id)
        while True:
            async with run._cond:
                pending = [event for event in run.events if int(event.id) > last_seq]
                if not pending and run.done:
                    return
                if not pending:
                    await run._cond.wait()
                    pending = [event for event in run.events if int(event.id) > last_seq]
            for event in pending:
                last_seq = int(event.id)
                yield event
            if run.done and not [event for event in run.events if int(event.id) > last_seq]:
                return
