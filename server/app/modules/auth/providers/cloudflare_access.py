"""Verifies the signed token Cloudflare Access adds to every request it admits.

The Engine's Worker forwards `Cf-Access-Jwt-Assertion`. The bare email header
is never trusted: the token's signature, audience, issuer and expiry are all
checked against the Access team's public keys.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import jwt

from app.modules.auth.config import get_access_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccessClaims:
    email: str
    sub: str


class AccessSignInError(Exception):
    """The token is missing, malformed, expired or not meant for this app."""


class AccessKeysUnavailableError(AccessSignInError):
    """Cloudflare's public keys could not be fetched, so the token cannot be checked."""


class _KeyResolver(Protocol):
    def get_signing_keys(self, refresh: bool = False) -> list[jwt.PyJWK]: ...


def access_configured() -> bool:
    settings = get_access_settings()
    return bool(settings.cf_access_team_domain and settings.cf_access_engine_aud)


@lru_cache
def _key_resolver(team_domain: str) -> _KeyResolver:
    # Caches the team's public keys so a request does not fetch them each time.
    return jwt.PyJWKClient(f"https://{team_domain}/cdn-cgi/access/certs", cache_keys=True)


# Unknown key ids can be spammed, so keys are refetched at most once a minute.
_MIN_REFRESH_SECONDS = 60.0
_refresh_lock = threading.Lock()
_last_refresh = 0.0


def _may_refresh() -> bool:
    global _last_refresh
    with _refresh_lock:
        if time.monotonic() - _last_refresh < _MIN_REFRESH_SECONDS:
            return False
        _last_refresh = time.monotonic()
        return True


def _signing_key(team_domain: str, token: str) -> jwt.PyJWK:
    key_id = jwt.get_unverified_header(token).get("kid")
    resolver = _key_resolver(team_domain)
    try:
        for key in resolver.get_signing_keys():
            if key.key_id == key_id:
                return key
        if _may_refresh():
            for key in resolver.get_signing_keys(refresh=True):
                if key.key_id == key_id:
                    return key
    except jwt.PyJWKClientConnectionError as exc:
        raise AccessKeysUnavailableError(str(exc)) from exc
    raise AccessSignInError("the token is signed with an unknown key")


def _verify(token: str, team_domain: str, audience: str) -> AccessClaims:
    try:
        signing_key = _signing_key(team_domain, token)
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=f"https://{team_domain}",
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise AccessSignInError(str(exc)) from exc
    email = claims.get("email")
    subject = claims.get("sub")
    if not isinstance(email, str) or not email or not isinstance(subject, str):
        # Service tokens carry no person, so they cannot act as an advisor.
        raise AccessSignInError("token has no signed-in person")
    return AccessClaims(email=email.lower(), sub=subject)


async def verify_access_jwt(token: str) -> AccessClaims:
    settings = get_access_settings()
    team_domain, audience = settings.cf_access_team_domain, settings.cf_access_engine_aud
    if not team_domain or not audience:
        raise AccessSignInError("Cloudflare Access is not configured")
    # PyJWKClient fetches keys with blocking I/O.
    return await asyncio.to_thread(_verify, token, team_domain, audience)
