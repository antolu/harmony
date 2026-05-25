from __future__ import annotations

import re
import time
import uuid
from typing import Any

import structlog
import structlog.contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


def get_trace_id(request: Request) -> str:
    x_request_id = request.headers.get("x-request-id")
    if x_request_id and _SAFE_ID_RE.match(x_request_id):
        return x_request_id

    traceparent = request.headers.get("traceparent")
    if traceparent:
        parts = traceparent.split("-")
        min_traceparent_parts = 2
        if len(parts) >= min_traceparent_parts:
            return parts[1]

    return str(uuid.uuid4())


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        trace_id = get_trace_id(request)
        request.state.trace_id = trace_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            endpoint=request.url.path,
            method=request.method,
        )

        start = time.monotonic()
        response = await call_next(request)
        latency_ms = round((time.monotonic() - start) * 1000, 2)

        structlog.contextvars.bind_contextvars(
            status_code=response.status_code,
            latency_ms=latency_ms,
        )

        structlog.get_logger().info("request")

        return response
