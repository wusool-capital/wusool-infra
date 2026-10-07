"""Request-scoped wiring and the two guards on the endpoints that spend
money.

There is deliberately no API key. Three of the five endpoints are called
mid-form from a public tool page, so any key that page carried would be
public — it would buy nothing and add a rotation obligation. The real
exposure is cost amplification (Bedrock and Firecrawl on an unauthenticated
POST), and what addresses that is an origin allowlist plus a per-IP
throttle.
"""

import base64
import hashlib
import hmac
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.persistence.database import get_sessionmaker
from app.modules.utilities import FixedWindowRateLimiter

logger = logging.getLogger(__name__)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Commits on a clean exit, rolls back on an exception.

    Never hand this session to a `BackgroundTasks` callable: it is committed
    and closed the moment the dependency resumes. Background work opens its
    own session through `bootstrap.py`.
    """
    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def client_ip(request: Request) -> str:
    """The **last** `X-Forwarded-For` entry, not the first.

    Caddy runs as a sibling container on the bridge network and uvicorn uses
    the default `forwarded_allow_ips="127.0.0.1"`, so `request.client.host`
    is Caddy's address for every request. Caddy appends the real peer to
    whatever the client sent, so the rightmost value is the trustworthy one
    — the leftmost is attacker-controlled.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


async def require_allowed_origin(origin: Annotated[str | None, Header()] = None) -> None:
    """Rejects a cross-site POST from a page we do not serve.

    Not a security boundary — `Origin` is trivially forged by a script — but
    it does stop another website embedding our tool and spending our Bedrock
    budget through its own visitors' browsers, which is the likely abuse.
    An empty allowlist disables the check, for local dev.
    """
    allowed = get_settings().lead_magnet_allowed_origins.split()
    if not allowed:
        return
    if origin is None or origin not in allowed:
        logger.warning("lead_magnet_origin_rejected origin=%s", origin)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "origin not allowed")


_limiter: FixedWindowRateLimiter | None = None


def _get_limiter() -> FixedWindowRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = FixedWindowRateLimiter(limit=get_settings().lead_magnet_rate_per_hour)
    return _limiter


async def rate_limit(request: Request) -> None:
    ip = client_ip(request)
    if not _get_limiter().check(ip):
        logger.warning("lead_magnet_rate_limited ip=%s", ip)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")


_read_limiter: FixedWindowRateLimiter | None = None


async def rate_limit_reads(request: Request) -> None:
    """Report page views: a separate, larger budget than `rate_limit`, so
    reading never uses up a reader's unlock."""
    global _read_limiter
    if _read_limiter is None:
        _read_limiter = FixedWindowRateLimiter(
            limit=get_settings().lead_magnet_report_reads_per_hour
        )
    ip = client_ip(request)
    if not _read_limiter.check(ip):
        logger.warning("lead_magnet_report_reads_limited ip=%s", ip)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")


_download_limiter: FixedWindowRateLimiter | None = None


async def rate_limit_downloads(request: Request) -> None:
    """PDF downloads: their own budget, so downloading never uses up a reader's
    unlock or another tool's submit behind the same office IP."""
    global _download_limiter
    if _download_limiter is None:
        _download_limiter = FixedWindowRateLimiter(
            limit=get_settings().lead_magnet_report_downloads_per_hour
        )
    ip = client_ip(request)
    if not _download_limiter.check(ip):
        logger.warning("lead_magnet_report_downloads_limited ip=%s", ip)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")


SANITY_SIGNATURE_HEADER = "sanity-webhook-signature"
_SANITY_SIGNATURE = re.compile(r"^t=(\d+)[, ]+v1=([^, ]+)$")
# Sanity retries twice, 30 s apart; anything older is a replay.
_SANITY_MAX_AGE_MS = 10 * 60 * 1000


def is_valid_sanity_signature(body: bytes, header: str | None, secret: str) -> bool:
    """Mirrors `@sanity/webhook`: the header is `t=<ms>,v1=<sig>`, where `sig`
    is the unpadded base64url HMAC-SHA256 of `"<t>.<raw body>"`. Must run on
    the raw bytes, since re-encoded JSON can differ."""
    if not header or not secret:
        return False
    match = _SANITY_SIGNATURE.match(header.strip())
    if match is None:
        return False
    timestamp, signature = match.groups()
    if abs(time.time() * 1000 - int(timestamp)) > _SANITY_MAX_AGE_MS:
        return False
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return hmac.compare_digest(expected, signature)
