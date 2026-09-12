"""Request-scoped wiring and the two guards on the endpoints that spend
money.

There is deliberately no API key. Three of the five endpoints are called
mid-form from a public tool page, so any key that page carried would be
public — it would buy nothing and add a rotation obligation. The real
exposure is cost amplification (Bedrock and Firecrawl on an unauthenticated
POST), and what addresses that is an origin allowlist plus a per-IP
throttle.
"""

import logging
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.persistence.database import get_sessionmaker

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


class FixedWindowRateLimiter:
    """Per-IP fixed window, in process.

    ponytail: one container per environment, so an in-process counter is
    accurate rather than merely convenient. It resets on deploy and does not
    survive a second instance — move it to Redis or a WAF rule only if
    either of those becomes true.
    """

    def __init__(self, *, limit: int, window_s: int = 3600) -> None:
        self._limit = limit
        self._window_s = window_s
        self._hits: dict[str, tuple[float, int]] = {}

    def check(self, key: str, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        started, count = self._hits.get(key, (now, 0))
        if now - started >= self._window_s:
            started, count = now, 0
        if count >= self._limit:
            return False
        self._hits[key] = (started, count + 1)
        return True


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
