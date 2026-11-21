"""Uniform error model: {"error": {"code", "message", ...extra}}. Messages never echo private content."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str = "", *, code: str | None = None, status: int | None = None, **extra: Any):
        super().__init__(message)
        self.message = message or self.__class__.__doc__ or ""
        if code:
            self.code = code
        if status:
            self.status = status
        self.extra = extra


class NotFound(AppError):
    """Not available."""

    status = 404
    code = "NOT_FOUND"


class Unauthorized(AppError):
    """Sign in to continue."""

    status = 401
    code = "UNAUTHORIZED"


class Forbidden(AppError):
    """Not permitted."""

    status = 403
    code = "FORBIDDEN"


class Conflict(AppError):
    """Conflicting state."""

    status = 409
    code = "CONFLICT"


class StaleRevision(Conflict):
    """Another change was saved first. Reload to see the newer work."""

    code = "STALE_REVISION"


class LeaseHeld(Conflict):
    """Another session has newer work."""

    code = "LEASE_HELD"


class PolicyLocked(AppError):
    """Independent application: no in-app lesson or hint access."""

    status = 423
    code = "TRANSFER_LOCKED"


class QuotaExhausted(AppError):
    """Not enough allowance to start this action."""

    status = 402
    code = "QUOTA_EXHAUSTED"


class ValidationFailed(AppError):
    status = 422
    code = "VALIDATION_FAILED"


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message, **exc.extra}},
    )
