"""ARQ worker: runs the same idempotent job handlers as inline mode.

    python -m arq worker.WorkerSettings        (from the repo root, with api installed)
"""

from __future__ import annotations

import asyncio

from arq import cron
from arq.connections import RedisSettings

import thinkfirst.models  # noqa: F401 — registers job handlers
from thinkfirst.config import get_settings
from thinkfirst.core.db import session_factory
from thinkfirst.core.jobs import run_job_by_id


async def run_job(ctx, job_id: str) -> None:
    await asyncio.to_thread(run_job_by_id, job_id)


def _purge() -> int:
    """Retention: delete audio past its 7-day cap. On Postgres the expired (id, owner) list comes from a
    content-free SECURITY DEFINER function; each deletion then runs inside that owner's RLS context."""
    from sqlalchemy import text

    from thinkfirst.modules.explain_back.service import purge_expired

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


class WorkerSettings:
    functions = [run_job]
    cron_jobs = [cron(purge_expired_audio, minute={0, 30})]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
