"""Metadata-only structured logging (override §3.9).

Only whitelisted metadata keys are emitted: IDs, route templates, timings, status/error codes.
Request/response bodies, prompts, transcripts and uploads are never logged.
"""

from __future__ import annotations

import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

ALLOWED_KEYS = {
    "request_id",
    "method",
    "route",
    "status",
    "duration_ms",
    "user_id",
    "job_id",
    "job_type",
    "error_code",
}


class MetadataOnlyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {"level": record.levelname, "logger": record.name, "event": record.msg if isinstance(record.msg, str) else "log"}
        for key in ALLOWED_KEYS:
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info and record.exc_info[0] is not None:
            data["exception_type"] = record.exc_info[0].__name__  # type only, never the message
        return json.dumps(data)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(MetadataOnlyFormatter())
    root = logging.getLogger("thinkfirst")
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        logging.getLogger("thinkfirst.http").info(
            "request",
            extra={
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),  # template, not the concrete URL
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response
