"""Server-side learning policy (non-negotiable rule: never rely on the client).

- Help ladder ordering and confirmed reveal (UC13/UC14).
- Transfer lock (UC15): while a task is in ``independent-transfer`` mode and not terminal, the subject denies
  hints, Professor tutoring, lesson/source content and prior feedback — across routes, tabs and devices.
- Capabilities derived from persisted state (blueprint capability list).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from thinkfirst.core.errors import AppError, PolicyLocked
from thinkfirst.modules.tutor.models import Task

TERMINAL_TASK = {"committed", "ended_assisted", "abandoned"}


class RevealConfirmationRequired(AppError):
    """Confirm to end this attempt and view the worked solution."""

    status = 409
    code = "REVEAL_CONFIRMATION_REQUIRED"


def active_lock(db: Session, owner_id: str, subject_id: str) -> Task | None:
    return db.scalar(select(Task).where(Task.owner_id == owner_id, Task.subject_id == subject_id,
                                        Task.mode == "independent-transfer", Task.status.not_in(TERMINAL_TASK)))


def lock_error(task: Task) -> PolicyLocked:
    return PolicyLocked(
        "Independent application: no in-app lesson or hint access until this attempt finishes or you switch to guided practice.",
        locked_task_id=task.id, session_id=task.session_id,
        offers=["return_to_task", "use_guided_help"],
    )


def assert_unlocked(db: Session, owner_id: str, subject_id: str) -> None:
    lock = active_lock(db, owner_id, subject_id)
    if lock is not None:
        raise lock_error(lock)


def next_level(task: Task, kind: str, confirm_reveal: bool) -> int:
    """Return the ladder level (1..5) this request is allowed to receive."""
    max_level = 5 if task.kind in ("expand",) else 3
    if kind == "dont_know":
        level = max(task.help_level, 1) if task.help_level else 1
    else:
        level = min(task.help_level + 1, max_level)
    if level == 5 and not confirm_reveal:
        raise RevealConfirmationRequired(next_level=5)
    return level


def capabilities(task: Task | None, lock: Task | None) -> dict:
    locked = lock is not None
    independent = task is not None and task.mode == "independent-transfer" and task.status not in TERMINAL_TASK
    return {
        "canCaptureAudio": task is not None and task.kind == "explain" and task.status not in TERMINAL_TASK,
        "canUsePaper": False,  # M7
        "canRunCode": False,  # M7
        "canReadSources": not locked,
        "canTutor": not locked and not independent,
        "canRevealTarget": task is not None and task.kind == "expand" and not locked,
        "canSubmit": task is not None and task.status not in TERMINAL_TASK and task.mode != "pending-commit",
        "canStartCostlyAction": not independent,
    }
