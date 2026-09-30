"""
Run store: an in-memory dict for live runs, plus JSON files on disk for
finished ones so they survive an API restart.

This is a local dev tool, not a multi-tenant service — that's the right
amount of infrastructure. A run's API key lives only inside the
closure of its background thread for the duration of that thread; it is
never written into RunState and is discarded when the thread exits.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Finished runs are written here so reports and result pages survive an API
# restart (the dict below is only the hot cache). Never contains an API key:
# RunState has no field for one.
RUNS_DIR = Path(os.getenv("DT_RUNS_DIR", "~/.digital-twins/runs")).expanduser()

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
            run = self._runs.get(run_id)
        return run or self._load(run_id)

    def persist(self, run: RunState) -> None:
        """Write a finished (done/error) run to disk; failures never break a run."""
        try:
            RUNS_DIR.mkdir(parents=True, exist_ok=True)
            (RUNS_DIR / f"{run.run_id}.json").write_text(
                json.dumps(run.snapshot(), ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not persist run %s (%s)", run.run_id, exc)

    def _load(self, run_id: str) -> RunState | None:
        # run_id comes from the URL; only accept canonical UUIDs as filenames.
        try:
            canonical = str(uuid.UUID(run_id))
            data = json.loads((RUNS_DIR / f"{canonical}.json").read_text(encoding="utf-8"))
        except (ValueError, OSError, json.JSONDecodeError):
            return None
        run = RunState(
            run_id=data["run_id"],
            max_rounds=data.get("max_rounds", 0),
            status=data["status"],
            log=data.get("log", []),
            result=data.get("result"),
            error=data.get("error"),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at"),
        )
        with self._lock:
            self._runs[run_id] = run
        return run


runs = RunStore()
