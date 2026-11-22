"""Standalone dev server for the Tutor module (no ThinkFirst needed).

    uvicorn tutor.api.app:app --reload --port 8010

Auth here is a dev stub: the `x-user-id` header (default "dev-user"). In ThinkFirst use the integration
module, which plugs in the real session cookie (see integration/thinkfirst/).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, Header

from ..service import TutorService, build_service
from .router import build_router, install_error_handler


@lru_cache
def get_service() -> TutorService:
    import os

    enqueue = None
    if os.environ.get("TUTOR_JOB_MODE") == "arq":
        from ..worker import enqueue_run

        enqueue = enqueue_run
    return build_service(enqueue=enqueue)


def dev_owner(x_user_id: str | None = Header(default=None)) -> str:
    return x_user_id or "dev-user"


def create_app() -> FastAPI:
    app = FastAPI(title="ThinkFirst Tutor", version="1.0.0", docs_url="/api/tutor/docs",
                  openapi_url="/api/tutor/openapi.json")
    app.include_router(build_router(get_service, dev_owner), prefix="/api")
    install_error_handler(app)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
