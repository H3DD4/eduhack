"""Background worker for long flows (ingestion, generation). Two options:

1. thread (default): runs inside the API process, fine for a pilot.
2. arq + Redis:      TUTOR_JOB_MODE=arq, then run `arq tutor.worker.WorkerSettings`.
   Runs are checkpointed, so a worker restart resumes at the failed node (POST /runs/{id}/resume).
"""

from __future__ import annotations

import asyncio

from .config import get_settings


async def tutor_run(ctx, run_id: str) -> str:
    from .service import build_service

    svc = ctx.get("svc") if isinstance(ctx, dict) else None
    if svc is None:
        svc = build_service()
        if isinstance(ctx, dict):
            ctx["svc"] = svc
    run = await asyncio.to_thread(svc.execute_run, run_id)
    return run["status"] if run else "missing"


def enqueue_run(run_id: str) -> None:
    async def _go():
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        await pool.enqueue_job("tutor_run", run_id, _job_id=f"tutor-{run_id}")
        await pool.close()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_go())
    else:  # called from inside an event loop: schedule it
        asyncio.ensure_future(_go())


try:  # pragma: no cover - only when arq is installed
    from arq.connections import RedisSettings

    class WorkerSettings:
        functions = [tutor_run]
        redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
        max_jobs = 4
        job_timeout = 60 * 30
except Exception:  # noqa: BLE001
    WorkerSettings = None  # type: ignore[assignment]
