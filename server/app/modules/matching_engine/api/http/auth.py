"""Shared-key gate for `/api/*` until the web app has a real login.

An unset `WEB_API_KEY` returns 503 rather than serving CRM data and deal
writes unauthenticated.
"""

import hmac

from fastapi import Header, HTTPException, status

from app.modules.matching_engine.api.http.schemas import ApiError
from app.modules.matching_engine.config import get_settings

_BEARER_PREFIX = "Bearer "

# Recorded as `approved_by` until decisions can be tied to a signed-in advisor.
WEB_ACTOR = "web"


def api_error(status_code: int, error: ApiError) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error.model_dump(mode="json"))


async def require_web_api_key(authorization: str | None = Header(default=None)) -> None:
    configured = get_settings().web_api_key
    if configured is None or not configured.get_secret_value():
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ApiError(code="web_disabled", message="The web app is not enabled on this server."),
        )
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            ApiError(code="unauthorized", message="Missing API key."),
        )
    token = authorization[len(_BEARER_PREFIX) :]
    if not hmac.compare_digest(token.encode(), configured.get_secret_value().encode()):
        raise api_error(
            status.HTTP_401_UNAUTHORIZED,
            ApiError(code="unauthorized", message="Invalid API key."),
        )
