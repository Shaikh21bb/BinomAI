"""Per-request tracing metadata for logs, responses, and support tickets."""

from __future__ import annotations

import re
from time import perf_counter
from uuid import uuid4

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings


logger = structlog.get_logger(__name__)
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _request_id(scope: Scope) -> str:
    supplied = Headers(scope=scope).get("x-request-id", "")
    if _SAFE_REQUEST_ID.fullmatch(supplied):
        return supplied
    return f"req_{uuid4().hex}"


class RequestContextMiddleware:
    """Attach a safe correlation ID to every HTTP request and response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        started_at = perf_counter()
        status_code = 500

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_context(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-App-Version"] = settings.APP_VERSION
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
            logger.info(
                "request_completed",
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
            )
        finally:
            structlog.contextvars.clear_contextvars()
