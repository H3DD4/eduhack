"""Idempotent background jobs with tracked status.

``enqueue`` returns the existing job when the idempotency key was already used, so retries never
duplicate work, evidence or charges. In ``inline`` mode the job runs immediately in-process (tests,
no-Docker dev); in ``arq`` mode the Redis worker (``/worker``) runs ``run_job``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from thinkfirst.config import get_settings
from thinkfirst.core.db import (
    Base,
    OwnedMixin,
    TimestampMixin,
    current_user_id,
    new_id,
    session_factory,
    utcnow,
)

log = logging.getLogger("thinkfirst.jobs")

QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED = "queued", "running", "succeeded", "failed", "cancelled"
TERMINAL = {SUCCEEDED, FAILED, CANCELLED}


class Job(Base, OwnedMixin, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = {"schema": "core"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default=QUEUED)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # IDs only, never content
    result: Mapped[dict] = mapped_column(JSON, default=dict)  # IDs / status only
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


JobHandler = Callable[[Session, Job], dict[str, Any]]
_registry: dict[str, JobHandler] = {}


class JobError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def job_handler(job_type: str):
    def deco(fn: JobHandler) -> JobHandler:
        _registry[job_type] = fn
        return fn

    return deco


def job_public(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "result": job.result,
        "error_code": job.error_code,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _can_commit_inline(db: Session) -> bool:
    return bool(
        db.info.get("is_request_session")
        and db.get_bind().dialect.name == "sqlite"
        and not db.in_nested_transaction()
    )


def _drain_inline(db: Session, first_job: Job) -> None:
    queue = [first_job.id]
    db.info["_in_inline_job"] = True
    try:
        while queue:
            jid = queue.pop(0)
            job = db.get(Job, jid)
            if job is None:
                continue
            _execute(db, job)
            if _can_commit_inline(db):
                db.commit()
            followups = db.info.pop("_inline_followup_jobs", [])
            if followups:
                queue.extend(followups)
    finally:
        db.info["_in_inline_job"] = False
        db.info.pop("_inline_followup_jobs", None)


def enqueue(db: Session, job_type: str, owner_id: str, payload: dict, idempotency_key: str) -> Job:
    existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
    if existing:
        if existing.owner_id != owner_id:
            raise PermissionError("idempotency key owned by another user")
        return existing
    job = Job(type=job_type, owner_id=owner_id, payload=payload, idempotency_key=idempotency_key)
    db.add(job)
    db.flush()
    if get_settings().job_mode == "inline":
        if db.info.get("_in_inline_job"):
            db.info.setdefault("_inline_followup_jobs", []).append(job.id)
        else:
            _drain_inline(db, job)
    else:
        _queue(db, job)
    return job


def _queue(db: Session, job: Job) -> None:
    """Queue ids carry the attempt number: ARQ silently drops an id it has already run, so a retry needs a new one."""
    db.info.setdefault("after_commit_jobs", []).append(f"{job.id}:{job.attempts or 0}")


def retry(db: Session, job: Job) -> Job:
    """Retry the *same* job (same ID) — never a new random job."""
    if job.status not in (FAILED,):
        return job
    job.status = QUEUED
    job.error_code = None
    db.flush()
    if get_settings().job_mode == "inline":
        if db.info.get("_in_inline_job"):
            db.info.setdefault("_inline_followup_jobs", []).append(job.id)
        else:
            _drain_inline(db, job)
    else:
        _queue(db, job)
    return job


def cancel(db: Session, job: Job) -> None:
    if job.status not in TERMINAL:
        job.status = CANCELLED
        db.flush()


def _execute(db: Session, job: Job) -> None:
    handler = _registry.get(job.type)
    if handler is None:
        job.status, job.error_code = FAILED, "UNKNOWN_JOB_TYPE"
        return
    if job.status == CANCELLED:
        return
    job.status = RUNNING
    job.attempts += 1
    if _can_commit_inline(db):
        db.commit()
    try:
        with db.begin_nested():
            result = handler(db, job)
        db.refresh(job)
        if job.status == CANCELLED:  # cancelled while running: late result is rejected
            return
        job.result = result or {}
        job.status = SUCCEEDED
    except JobError as exc:
        job.status, job.error_code = FAILED, exc.code
    except Exception:  # noqa: BLE001 - metadata-only logging, no content
        log.exception("job failed", extra={"job_id": job.id, "job_type": job.type})
        job.status, job.error_code = FAILED, "INTERNAL_ERROR"
    db.flush()


def run_job_by_id(job_id: str) -> None:
    """Entry point for the ARQ worker."""
    factory = session_factory()
    with factory() as db:
        if db.get_bind().dialect.name == "postgresql":
            from sqlalchemy import text

            owner = db.execute(text("select core.job_owner(:jid)"), {"jid": job_id}).scalar()
            db.rollback()  # next transaction begins inside the owner's RLS context
            if not owner:
                return
            db.info["user_id"] = owner
        job = db.get(Job, job_id)
        if job is None or job.status in TERMINAL:
            return
        db.info["user_id"] = job.owner_id
        token = current_user_id.set(job.owner_id)
        try:
            _execute(db, job)
            db.commit()
        finally:
            current_user_id.reset(token)


async def enqueue_remote(ids: list[str]) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    for qid in ids:
        await pool.enqueue_job("run_job", qid.partition(":")[0], _job_id=qid)
    await pool.close()
