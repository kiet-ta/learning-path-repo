"""
Performance Middleware - API Layer

Adds X-Process-Time header to every response and emits a WARNING log
for requests that exceed a configurable slow-request threshold.

Threshold default: 2000 ms.  Override via SLOW_REQUEST_THRESHOLD_MS env var.
"""
import logging
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger("api.performance")

_SLOW_THRESHOLD_MS: float = float(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "2000"))


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Measures wall-clock processing time for every request.

    Adds:
      - X-Process-Time: <ms>ms  response header
      - Warning log when processing exceeds SLOW_REQUEST_THRESHOLD_MS
    """

    def __init__(self, app: ASGIApp, slow_threshold_ms: float = _SLOW_THRESHOLD_MS) -> None:
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response: Response = await call_next(request)
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)

        response.headers["X-Process-Time"] = f"{elapsed_ms}ms"

        if elapsed_ms > self.slow_threshold_ms:
            logger.warning(
                "Slow request detected",
                extra={
                    "structured_context": {
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": elapsed_ms,
                        "threshold_ms": self.slow_threshold_ms,
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )

        return response

