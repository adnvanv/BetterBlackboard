"""Tiny in-memory progress tracker for the current/last scrape.

Lives in process memory (single uvicorn worker), reset on every new run.
The frontend reads it from /api/health to show 'Scraping CSCE587 (2/4)'-style
status under the Scrape Now button.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Progress:
    run_id: Optional[int] = None
    stage: str = ""           # e.g. "Logging in", "Found 4 courses"
    current: int = 0          # courses scraped so far
    total: int = 0            # total courses to scrape
    detail: str = ""          # e.g. "CSCE 587"
    finished: bool = False
    success: Optional[bool] = None
    message: str = ""         # final summary on completion


_lock = threading.Lock()
_state = Progress()


def reset(run_id: int) -> None:
    global _state
    with _lock:
        _state = Progress(run_id=run_id, stage="Starting")


def set_stage(stage: str, detail: str = "") -> None:
    with _lock:
        _state.stage = stage
        _state.detail = detail


def set_totals(total: int) -> None:
    with _lock:
        _state.total = total


def step(current: int, detail: str = "") -> None:
    with _lock:
        _state.current = current
        if detail:
            _state.detail = detail


def finish(success: bool, message: str) -> None:
    with _lock:
        _state.finished = True
        _state.success = success
        _state.message = message
        _state.stage = "Done"


def snapshot() -> dict:
    with _lock:
        return {
            "runId": _state.run_id,
            "stage": _state.stage,
            "current": _state.current,
            "total": _state.total,
            "detail": _state.detail,
            "finished": _state.finished,
            "success": _state.success,
            "message": _state.message,
        }
