from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

API_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, development_docs: bool = False) -> None:
        self.app = app
        self.development_docs = development_docs

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.update(API_HEADERS)
                if self.development_docs and scope["path"] == "/docs":
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                        "script-src https://cdn.jsdelivr.net 'unsafe-inline'; "
                        "style-src https://cdn.jsdelivr.net 'unsafe-inline'; "
                        "img-src https://fastapi.tiangolo.com data:; connect-src 'self'"
                    )
            await send(message)

        await self.app(scope, receive, secure_send)
