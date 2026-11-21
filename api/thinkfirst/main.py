"""FastAPI app: modular monolith. All routes are mounted under /api (Next.js proxies same-origin)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import thinkfirst.models  # noqa: F401 — registers models, jobs, event handlers
from thinkfirst.core.errors import AppError, app_error_handler
from thinkfirst.core.logging import RequestLogMiddleware, setup_logging
from thinkfirst.core.router import router as core_router
from thinkfirst.modules.billing.router import router as billing_router
from thinkfirst.modules.diagnostic.router import router as diagnostic_router
from thinkfirst.modules.explain_back.router import router as explain_router
from thinkfirst.modules.identity.router import router as identity_router
from thinkfirst.modules.student_profile.router import router as learner_router
from thinkfirst.modules.tutor.router import router as tutor_router
from thinkfirst.modules.workspaces.router import router as workspaces_router

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT = {"/api/auth/google/callback"}


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="ThinkFirst API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    @app.middleware("http")
    async def csrf_and_jobs(request: Request, call_next):
        # CSRF: SameSite=Lax cookie + a custom header simple cross-site forms cannot send.
        if request.method in MUTATING and request.url.path not in CSRF_EXEMPT:
            if request.headers.get("x-thinkfirst-client") != "web":
                return JSONResponse(status_code=403, content={"error": {"code": "CSRF", "message": "Missing client header."}})
        response = await call_next(request)
        return response

    app.add_middleware(RequestLogMiddleware)
    for r in (core_router, identity_router, billing_router, workspaces_router, tutor_router, explain_router, learner_router,
              diagnostic_router):
        app.include_router(r, prefix="/api")

    return app


app = create_app()
