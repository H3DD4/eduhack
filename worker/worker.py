"""ARQ worker: runs the same idempotent job handlers as inline mode.

    python -m arq worker.WorkerSettings        (from the repo root, with api installed)
"""

from __future__ import annotations

import asyncio
import logging

from arq import cron
from arq.connections import RedisSettings

import thinkfirst.models  # noqa: F401 — registers job handlers
from thinkfirst.config import get_settings
from thinkfirst.core.db import session_factory
from thinkfirst.core.jobs import run_job_by_id

log = logging.getLogger("thinkfirst.worker")


async def run_job(ctx, job_id: str) -> None:
    await asyncio.to_thread(run_job_by_id, job_id)


def _purge() -> int:
    """Retention: delete audio past its 7-day cap. On Postgres the expired (id, owner) list comes from a
    content-free SECURITY DEFINER function; each deletion then runs inside that owner's RLS context."""
    from sqlalchemy import text

    from thinkfirst.modules.tutor.explain_back.service import purge_expired

    factory = session_factory()
    with factory() as db:
        if db.get_bind().dialect.name != "postgresql":
            n = purge_expired(db)
            db.commit()
            return n
        owners = {row.owner_id for row in db.execute(text("select * from explain_back.expired_takes()"))}
    n = 0
    for owner in owners:
        with factory() as db:
            db.info["user_id"] = owner
            n += purge_expired(db)
            db.commit()
    return n


async def purge_expired_audio(ctx) -> None:
    await asyncio.to_thread(_purge)


def _unfinished() -> list[str]:
    from sqlalchemy import text

    with session_factory()() as db:
        if db.get_bind().dialect.name != "postgresql":
            return []
        return [f"{r.id}:{r.attempts}" for r in db.execute(text("select * from core.unfinished_jobs()"))]


async def recover(ctx) -> None:
    """Every minute: jobs still queued in the database are (re)queued, so a crash, a lost queue message or a worker that
    started before the migrations never leaves a student stuck. Same id => the queue ignores jobs already waiting/running."""
    try:
        ids = await asyncio.to_thread(_unfinished)
    except Exception:  # noqa: BLE001
        log.exception("job recovery failed")
        return
    for qid in ids:
        await ctx["redis"].enqueue_job("run_job", qid.partition(":")[0], _job_id=qid)


class WorkerSettings:
    keep_result = 600  # pace re-runs of a job that keeps crashing
    job_timeout = 3600  # indexing a whole book takes several minutes (ARQ's default is 300 s)
    functions = [run_job]
    cron_jobs = [cron(purge_expired_audio, minute={0, 30}), cron(recover, second=5, run_at_startup=True)]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
