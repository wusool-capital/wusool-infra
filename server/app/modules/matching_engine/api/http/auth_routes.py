"""`/api/auth/*`: Sign in with Slack for the web app, restricted to the
workspace the Toolkit bot is installed in.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.modules.matching_engine.api.http.auth import (
    CurrentUser,
    api_error,
    api_key_enabled,
    set_session_cookie,
    slack_sign_in_enabled,
)
from app.modules.matching_engine.api.http.schemas import (
    ApiError,
    ApiErrorResponse,
    AuthConfigResponse,
    MeResponse,
)
from app.modules.matching_engine.api.http.session import SESSION_COOKIE, WebSession
from app.modules.matching_engine.api.http.slack_identity import (
    SlackSignInError,
    authorize_url,
    identity_from_code,
    workspace_team_id,
)
from app.modules.matching_engine.config import get_settings

logger = logging.getLogger(__name__)

_STATE_COOKIE = "wusool_signin_state"
_STATE_PATH = "/api/auth"
_APP_HOME = "/app/"

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    generate_unique_id_function=lambda route: route.name,
)

SignInError = Literal["denied", "expired", "wrong_workspace", "failed"]


def _safe_next(path: str | None) -> str:
    # Only paths inside the app: anything else could bounce people to another site.
    if path and path.startswith("/app") and not path.startswith("//"):
        return path
    return _APP_HOME


def _fail(reason: SignInError) -> RedirectResponse:
    response = RedirectResponse(
        f"{_APP_HOME}?{urlencode({'signin_error': reason})}", status.HTTP_303_SEE_OTHER
    )
    response.delete_cookie(_STATE_COOKIE, path=_STATE_PATH)
    return response


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config() -> AuthConfigResponse:
    return AuthConfigResponse(slack_sign_in=slack_sign_in_enabled(), api_key=api_key_enabled())


@router.get("/me", response_model=MeResponse, responses={401: {"model": ApiErrorResponse}})
async def get_me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        slack_user_id=user.slack_user_id,
        name=user.name,
        via="slack" if user.slack_user_id else "key",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/slack/login", include_in_schema=False)
async def slack_login(next_path: str | None = Query(default=None, alias="next")) -> Response:
    if not slack_sign_in_enabled():
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ApiError(code="web_disabled", message="Sign in with Slack isn't set up."),
        )
    state = secrets.token_urlsafe(24)
    try:
        team_id: str | None = await workspace_team_id()
    except Exception:
        logger.warning("slack_workspace_lookup_failed")
        team_id = None
    response = RedirectResponse(authorize_url(state=state, team_id=team_id))
    # Lax: Slack's redirect back is a top-level GET, which still carries it.
    response.set_cookie(
        _STATE_COOKIE,
        f"{state}|{_safe_next(next_path)}",
        max_age=600,
        path=_STATE_PATH,
        httponly=True,
        secure=(get_settings().web_public_url or "").startswith("https://"),
        samesite="lax",
    )
    return response


@router.get("/slack/callback", include_in_schema=False)
async def slack_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    if error is not None:
        return _fail("denied")
    expected, _, next_path = (request.cookies.get(_STATE_COOKIE) or "").partition("|")
    if not code or not state or not expected or not secrets.compare_digest(state, expected):
        return _fail("expired")
    try:
        identity = await identity_from_code(code)
        allowed_team = await workspace_team_id()
    except SlackSignInError as exc:
        logger.warning("slack_sign_in_failed reason=%s", exc)
        return _fail("failed")
    if identity.team_id != allowed_team:
        return _fail("wrong_workspace")

    now = datetime.now(UTC)
    response = RedirectResponse(_safe_next(next_path), status.HTTP_303_SEE_OTHER)
    set_session_cookie(
        response,
        WebSession(
            user_id=identity.user_id,
            team_id=identity.team_id,
            name=identity.name,
            expires_at=now + timedelta(days=get_settings().web_session_days),
            checked_at=now,
        ),
    )
    response.delete_cookie(_STATE_COOKIE, path=_STATE_PATH)
    return response
