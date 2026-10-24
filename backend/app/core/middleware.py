"""Runs around every request (D-021, D-124).

1. Gives the request a fresh ID (never the caller's), used in logs and errors.
2. Turns any crash into a plain 500 problem (no details shown).
3. Adds the security headers.
4. Writes one access log line with the route template (for example
   /api/v1/verify/{code}), never the real path or query string, which can
   hold verification codes.
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.routing import Match

from app.core.errors import internal_error
from app.core.logs import request_id_var

logger = logging.getLogger("schoolflow.access")
crash_logger = logging.getLogger("schoolflow.errors")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# The API returns JSON only: nothing may run, load or frame it.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
HSTS = "max-age=63072000; includeSubDomains"
DOCS_PATHS = ("/api/v1/docs", "/api/v1/openapi.json")


def route_template(request: Request) -> str:
    for route in request.app.router.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return str(getattr(route, "path", "unknown"))
    return "unmatched"


def add_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(  # pyright: ignore[reportUnusedFunction]
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid.uuid4())
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                crash_logger.exception("Unhandled error")
                response = internal_error()

            response.headers["X-Request-ID"] = request_id
            for name, value in SECURITY_HEADERS.items():
                response.headers[name] = value
            if request.url.path not in DOCS_PATHS:
                response.headers["Content-Security-Policy"] = API_CSP
            response.headers.setdefault("Cache-Control", "no-store")
            if request.app.state.app_env != "local":
                response.headers["Strict-Transport-Security"] = HSTS

            logger.info(
                "request",
                extra={
                    "fields": {
                        "method": request.method,
                        "route": route_template(request),
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "school_id": getattr(request.state, "school_id", None),
                        "user_id": getattr(request.state, "user_id", None),
                    }
                },
            )
            return response
        finally:
            request_id_var.reset(token)
