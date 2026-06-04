"""
Request-tracing middleware.

Generates a UUID v4 trace_id for every inbound request, attaches it to
``request.state.trace_id``, returns it in the ``X-Trace-Id`` response header,
and emits a structured log line on completion with method, path, status,
duration, and trace_id.
"""
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("alrm.trace")


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        trace_id = uuid.uuid4().hex
        request.state.trace_id = trace_id

        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        response.headers["X-Trace-Id"] = trace_id

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            trace_id=trace_id,
        )

        return response
