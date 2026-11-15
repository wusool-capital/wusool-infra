"""Who is using `/api/*`: a Slack-signed-in advisor (the session cookie), or,
as a fallback for local use, anyone holding the shared `WEB_API_KEY`.

Neither configured returns 503 rather than serving CRM data and deal writes
unauthenticated.
"""

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Response, status

from app.modules.auth import is_active_member
from app.modules.matching_engine.api.http.schemas import ApiError
from app.modules.matching_engine.api.http.session import (
    RECHECK_AFTER,
    SESSION_COOKIE,
    WebSession,
    decode_session,
    encode_session,
    renewed,
)
from app.modules.matching_engine.config import get_settings

_BEARER_PREFIX = "Bearer "
# Header a cookie-authenticated write must carry; another site's page can't send it.
CLIENT_HEADER = "X-Wusool-Client"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Recorded as the actor when the shared key, not a person, made the call.
WEB_ACTOR = "web"


@dataclass(frozen=True)
class WebUser:
    """`slack_user_id` is the same ID Slack's `/find-match` records, so web and
    Slack activity line up by person. None for the shared key."""

    slack_user_id: str | None
    name: str | None

    @property
    def actor(self) -> str:
        return self.slack_user_id or WEB_ACTOR


def api_error(status_code: int, error: ApiError) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error.model_dump(mode="json"))


def slack_sign_in_enabled() -> bool:
    s = get_settings()
    return bool(
        s.slack_client_id and s.slack_client_secret and s.web_session_secret and s.web_public_url
    )


def api_key_enabled() -> bool:
    key = get_settings().web_api_key
    return key is not None and bool(key.get_secret_value())


def _unauthorized(message: str) -> HTTPException:
    return api_error(status.HTTP_401_UNAUTHORIZED, ApiError(code="unauthorized", message=message))


def set_session_cookie(response: Response, session: WebSession) -> None:
    settings = get_settings()
    secret = settings.web_session_secret
    if secret is None:
        return
    response.set_cookie(
        SESSION_COOKIE,
        encode_session(session, secret.get_secret_value()),
        max_age=settings.web_session_days * 86400,
        path="/",
        httponly=True,
        secure=(settings.web_public_url or "").startswith("https://"),
        samesite="lax",
    )


async def _session_user(request: Request, response: Response) -> WebUser | None:
    settings = get_settings()
    secret = settings.web_session_secret
    token = request.cookies.get(SESSION_COOKIE)
    if secret is None or not token or not slack_sign_in_enabled():
        return None
    now = datetime.now(UTC)
    session = decode_session(token, secret.get_secret_value(), now=now)
    if session is None:
        return None
    if request.method not in _SAFE_METHODS and request.headers.get(CLIENT_HEADER) != "web":
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            ApiError(code="unauthorized", message="Missing client header."),
        )
    if now - session.checked_at > RECHECK_AFTER:
        active = await is_active_member(session.user_id)
        if active is False:
            response.delete_cookie(SESSION_COOKIE, path="/")
            raise _unauthorized("Your Slack account is no longer active in the workspace.")
        if active:
            set_session_cookie(response, renewed(session, now=now, days=settings.web_session_days))
    return WebUser(slack_user_id=session.user_id, name=session.name)


def _key_user(authorization: str | None) -> WebUser | None:
    configured = get_settings().web_api_key
    if not api_key_enabled() or configured is None or authorization is None:
        return None
    if not authorization.startswith(_BEARER_PREFIX):
        return None
    token = authorization[len(_BEARER_PREFIX) :]
    if hmac.compare_digest(token.encode(), configured.get_secret_value().encode()):
        return WebUser(slack_user_id=None, name=None)
    raise _unauthorized("Invalid API key.")


async def require_web_user(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None, include_in_schema=False),
) -> WebUser:
    if not slack_sign_in_enabled() and not api_key_enabled():
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ApiError(code="web_disabled", message="The web app is not enabled on this server."),
        )
    user = await _session_user(request, response) or _key_user(authorization)
    if user is None:
        raise _unauthorized("Sign in to continue.")
    return user


CurrentUser = Annotated[WebUser, Depends(require_web_user)]
