import logging
from time import perf_counter

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app.http")
HTTP_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"}


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = perf_counter()
        status = 500

        async def track_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, track_status)
        finally:
            method = scope.get("method", "")
            logger.info(
                "HTTP request",
                extra={
                    "method": method if method in HTTP_METHODS else "OTHER",
                    "route": getattr(scope.get("route"), "path", "[unmatched]"),
                    "status": status,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
