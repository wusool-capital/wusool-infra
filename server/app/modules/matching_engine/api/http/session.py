"""The web app's signed session: who signed in with Slack, until when, and when
Slack last confirmed they're still in the workspace. Stateless (an HMAC-signed
cookie), so a restart or deploy never signs anyone out.
"""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, ValidationError

SESSION_COOKIE = "wusool_session"
# Slack is asked again at most this often whether the person is still active.
RECHECK_AFTER = timedelta(days=1)


class WebSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    team_id: str
    name: str | None
    expires_at: datetime
    checked_at: datetime


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def encode_session(session: WebSession, secret: str) -> str:
    payload = _b64(session.model_dump_json().encode())
    return f"{payload}.{_sign(payload, secret)}"


def decode_session(token: str, secret: str, *, now: datetime) -> WebSession | None:
    """None for anything tampered with, malformed or expired."""
    payload, _, signature = token.partition(".")
    if not payload or not hmac.compare_digest(signature, _sign(payload, secret)):
        return None
    try:
        session = WebSession.model_validate_json(_unb64(payload))
    except (ValueError, ValidationError):
        return None
    return session if session.expires_at > now else None


def renewed(session: WebSession, *, now: datetime, days: int) -> WebSession:
    """Slides the expiry forward after a fresh check with Slack."""
    return session.model_copy(update={"expires_at": now + timedelta(days=days), "checked_at": now})
