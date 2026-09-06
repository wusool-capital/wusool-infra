"""Desktop-push authentication: a single shared `DESKTOP_API_KEY`, unlike
matching_engine's dev/prod dual-key Slack target resolution — the desktop
app talks to exactly one backend.

`Settings.desktop_api_key` has no default, so a misconfigured deploy (the
env var unset) already fails at `Settings()` construction time, at process
startup — confirmed against `config.py`. This dependency's mismatch check
below is the only other place a bad key can surface, and only at request
time, for a key that's set but wrong.
"""

import hmac

from fastapi import Header

from app.modules.meetings.application.errors import InvalidDesktopApiKeyError
from app.modules.meetings.config import get_settings

_BEARER_PREFIX = "Bearer "


async def require_desktop_api_key(authorization: str | None = Header(default=None)) -> None:
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise InvalidDesktopApiKeyError("Missing or malformed Authorization header")

    token = authorization[len(_BEARER_PREFIX) :]
    if not hmac.compare_digest(token, get_settings().desktop_api_key):
        raise InvalidDesktopApiKeyError("Invalid desktop API key")
