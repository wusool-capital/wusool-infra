"""Sign in with Slack (OpenID Connect) against the Toolkit's own Slack app, and
the bot-token checks that keep a session tied to a current workspace member.
"""

import logging
from dataclasses import dataclass
from urllib.parse import urlencode

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.matching_engine.config import get_settings

logger = logging.getLogger(__name__)

_AUTHORIZE_URL = "https://slack.com/openid/connect/authorize"


@dataclass(frozen=True)
class SlackIdentity:
    user_id: str
    team_id: str
    name: str | None


class SlackSignInError(Exception):
    """Slack refused the sign-in, or answered with something unusable."""


def callback_url() -> str:
    base = (get_settings().web_public_url or "").rstrip("/")
    return f"{base}/api/auth/slack/callback"


def authorize_url(*, state: str, team_id: str | None) -> str:
    params = {
        "response_type": "code",
        "scope": "openid profile",
        "client_id": get_settings().slack_client_id or "",
        "state": state,
        "redirect_uri": callback_url(),
    }
    if team_id:
        # Skips Slack's workspace picker for people in several workspaces.
        params["team"] = team_id
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


async def identity_from_code(code: str) -> SlackIdentity:
    settings = get_settings()
    secret = settings.slack_client_secret
    try:
        token = await AsyncWebClient().openid_connect_token(
            client_id=settings.slack_client_id or "",
            client_secret=secret.get_secret_value() if secret else "",
            code=code,
            redirect_uri=callback_url(),
        )
        access_token = token.get("access_token")
        if not isinstance(access_token, str):
            raise SlackSignInError("no access token")
        info = await AsyncWebClient(token=access_token).openid_connect_userInfo()
    except SlackApiError as exc:
        raise SlackSignInError(str(exc.response.get("error"))) from exc
    user_id = info.get("https://slack.com/user_id")
    team_id = info.get("https://slack.com/team_id")
    name = info.get("name")
    if not isinstance(user_id, str) or not isinstance(team_id, str):
        raise SlackSignInError("identity missing user or team")
    return SlackIdentity(
        user_id=user_id, team_id=team_id, name=name if isinstance(name, str) else None
    )


def _bot() -> AsyncWebClient:
    return AsyncWebClient(token=get_settings().slack_bot_token)


# The bot's workspace never changes while the process runs.
_team_id_cache: dict[str, str] = {}


async def workspace_team_id() -> str:
    """The workspace the Toolkit bot is installed in: the only one allowed in."""
    if "team_id" not in _team_id_cache:
        team_id = (await _bot().auth_test()).get("team_id")
        if not isinstance(team_id, str):
            raise SlackSignInError("bot token has no team")
        _team_id_cache["team_id"] = team_id
    return _team_id_cache["team_id"]


async def is_active_member(user_id: str) -> bool | None:
    """False once Slack says the person was removed or deactivated; None when
    Slack can't be asked, so an outage doesn't sign everyone out."""
    try:
        user = (await _bot().users_info(user=user_id)).get("user")
    except SlackApiError as exc:
        error = exc.response.get("error")
        if error == "user_not_found":
            return False
        if error == "missing_scope":
            # Without users:read nobody is ever signed out for leaving Slack.
            logger.warning("slack_member_check_needs_users_read_scope")
        else:
            logger.warning("slack_member_check_failed user_id=%s error=%s", user_id, error)
        return None
    except Exception:
        logger.warning("slack_member_check_failed user_id=%s", user_id)
        return None
    if not isinstance(user, dict):
        return None
    return not user.get("deleted", False)
