"""
Logging Middleware - API Layer

Emits one structured JSON log line per request/response pair containing:
  method, path, status_code, duration_ms, client_ip, request_id

A unique request_id (UUID) is generated per request and added to the
response headers as X-Request-ID for end-to-end traceability.
"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger("api.access")

# Paths excluded from access logging (health / readiness probes)
_SKIP_PATHS = {"/api/v1/health", "/api/v1/health/db", "/docs", "/redoc", "/openapi.json"}


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that logs every HTTP request and response.

    Attaches a X-Request-ID header to every response.
    Skips health-check paths to keep logs clean.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        # Attach request_id to request state so handlers can reference it
        request.state.request_id = request_id

        response: Response = await call_next(request)

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        if request.url.path not in _SKIP_PATHS:
            logger.info(
                "HTTP request",
                extra={
                    "structured_context": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "client_ip": _get_client_ip(request),
                        "request_id": request_id,
                        "user_agent": request.headers.get("user-agent", ""),
                    }
                },
            )

        return response


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For from reverse proxy."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

