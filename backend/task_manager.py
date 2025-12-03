# backend/task_manager.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict, Optional, Awaitable, Callable

from fastapi import Request


class TaskCancelledError(Exception):
    """Raised when a task was cancelled or client disconnected."""
    pass

@dataclass
class TaskState:
    id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    cancelled: bool = False
    stage: str = "queued"  # <--- NEW (queued / extracting / summary / flashcards / script / audio / done / error)

@dataclass
class TaskState:
    id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    cancelled: bool = False
    # place for future fields:
    # status: str = "running"
    # result: Optional[dict] = None


_TASKS: Dict[str, TaskState] = {}
_LOCK = Lock()


def create_task(task_id: str) -> TaskState:
    """Register a new task with given id (frontend generates it)."""
    with _LOCK:
        state = TaskState(id=task_id)
        _TASKS[task_id] = state
        return state


def cancel_task(task_id: str) -> None:
    """Mark a task as cancelled (called by /api/cancel)."""
    with _LOCK:
        if task_id in _TASKS:
            _TASKS[task_id].cancelled = True


def is_cancelled(task_id: str) -> bool:
    with _LOCK:
        state = _TASKS.get(task_id)
        return bool(state and state.cancelled)


def clear_task(task_id: str) -> None:
    """Remove task from registry (cleanup when finished)."""
    with _LOCK:
        _TASKS.pop(task_id, None)


def get_task(task_id: str) -> Optional[TaskState]:
    with _LOCK:
        return _TASKS.get(task_id)

def set_stage(task_id: str, stage: str) -> None:
    with _LOCK:
        state = _TASKS.get(task_id)
        if state:
            state.stage = stage


def get_stage(task_id: str) -> Optional[str]:
    with _LOCK:
        state = _TASKS.get(task_id)
        return state.stage if state else None


def get_queue_position(task_id: str) -> Optional[int]:
    """
    Return 0-based position in queue among not-finished tasks.
    0 = first (currently running or next),
    1 = one task ahead, etc.
    None = task unknown or already fully finished and cleaned.
    """
    with _LOCK:
        me = _TASKS.get(task_id)
        if not me:
            return None

        # Pending = not done / error / cancelled
        pending = [
            t for t in _TASKS.values()
            if t.stage not in ("done", "error", "cancelled")
        ]
        # Oldest first
        pending.sort(key=lambda t: t.created_at)

        for idx, t in enumerate(pending):
            if t.id == task_id:
                return idx

        return None

# ---- cancellation helper -------------------------------------------------


def make_cancel_check(
    request: Request,
    task_id: str,
) -> Callable[[], Awaitable[None]]:
    """
    Return an async function cancel_check() that:
    - raises TaskCancelledError if HTTP disconnected
    - or task was cancelled via /api/cancel
    """

    async def cancel_check() -> None:
        # client disconnected
        if await request.is_disconnected():
            raise TaskCancelledError()

        # explicit cancel from UI
        if is_cancelled(task_id):
            raise TaskCancelledError()

    return cancel_check
