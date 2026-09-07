"""
In-memory run store.

This is a local dev tool, not a multi-tenant service — an in-memory dict is
the right amount of infrastructure. A run's API key lives only inside the
closure of its background thread for the duration of that thread; it is
never written into RunState and is discarded when the thread exits.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

RunStatus = Literal["running", "done", "error"]


@dataclass
class RunState:
    run_id: str
    max_rounds: int = 0
    status: RunStatus = "running"
    log: list[dict] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append_event(self, event: dict) -> None:
        with self.lock:
            self.log.append(event)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "run_id": self.run_id,
                "max_rounds": self.max_rounds,
                "status": self.status,
                "log": list(self.log),
                "result": self.result,
                "error": self.error,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            }


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()

    def create(self, max_rounds: int = 0) -> RunState:
        run = RunState(run_id=str(uuid.uuid4()), max_rounds=max_rounds)
        with self._lock:
            self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> RunState | None:
        with self._lock:
            return self._runs.get(run_id)


runs = RunStore()
