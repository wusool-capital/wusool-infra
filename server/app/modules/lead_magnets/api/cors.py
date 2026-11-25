"""CORS for the lead-magnet POST endpoints, so the marketing site can call them
from the browser.

A middleware rather than a route dependency: the `OPTIONS` preflight has no
route (405) and never reaches `require_allowed_origin`, and the 403/422/429
responses the site maps to messages are invisible to the browser without
`Access-Control-Allow-Origin`. Origins come from the same
`LEAD_MAGNET_ALLOWED_ORIGINS` list `require_allowed_origin` checks, matched
exactly. An empty list sends no CORS headers, never `*`. No credentials.
"""

from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.modules.lead_magnets.config import get_settings

LEAD_MAGNET_POST_PATHS = frozenset(
    {
        "/enrich",
        "/analyze",
        "/compare",
        "/submit-lead",
        "/readiness/score",
        "/benchmark",
    }
)
_PREFLIGHT_MAX_AGE = "600"


class LeadMagnetCors:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] not in LEAD_MAGNET_POST_PATHS:
            await self.app(scope, receive, send)
            return
        origin = Headers(scope=scope).get("origin")
        if origin is None or origin not in get_settings().lead_magnet_allowed_origins.split():
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS":
            response = Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "POST",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Max-Age": _PREFLIGHT_MAX_AGE,
                    "Vary": "Origin",
                },
            )
            await response(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Drop one the inner app added, so the browser never sees two values.
                headers = [
                    h
                    for h in message.get("headers", [])
                    if h[0].lower() != b"access-control-allow-origin"
                ]
                headers.append((b"access-control-allow-origin", origin.encode("latin-1")))
                headers.append((b"vary", b"Origin"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cors)
