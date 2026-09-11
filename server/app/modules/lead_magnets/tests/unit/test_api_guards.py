"""The two guards on the endpoints that spend money.

There is no API key by design: three of the five endpoints are called
mid-form from a public page, so any key the page carried would be public.
"""

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.modules.lead_magnets.api import dependencies as deps
from app.modules.lead_magnets.api.dependencies import (
    FixedWindowRateLimiter,
    client_ip,
    rate_limit,
    require_allowed_origin,
)
from app.modules.lead_magnets.config import get_settings


@pytest.fixture(autouse=True)
def _reset_limiter():
    deps._limiter = None
    get_settings.cache_clear()
    yield
    deps._limiter = None
    get_settings.cache_clear()


def _app(dependency) -> TestClient:
    app = FastAPI()

    @app.post("/t", dependencies=[Depends(dependency)])
    async def _t() -> dict:
        return {"ok": True}

    return TestClient(app)


def test_empty_allowlist_disables_the_origin_check(monkeypatch) -> None:
    """Local dev must still work without configuring an origin."""
    monkeypatch.setenv("LEAD_MAGNET_ALLOWED_ORIGINS", "")
    get_settings.cache_clear()
    assert _app(require_allowed_origin).post("/t").status_code == 200


def test_disallowed_origin_is_rejected(monkeypatch) -> None:
    """Stops another site embedding our tool and spending our Bedrock budget
    through its own visitors' browsers."""
    monkeypatch.setenv("LEAD_MAGNET_ALLOWED_ORIGINS", "https://tools.wusoolcapital.com")
    get_settings.cache_clear()
    client = _app(require_allowed_origin)

    assert client.post("/t", headers={"Origin": "https://evil.example"}).status_code == 403
    # A missing Origin is rejected too once an allowlist exists.
    assert client.post("/t").status_code == 403
    assert (
        client.post("/t", headers={"Origin": "https://tools.wusoolcapital.com"}).status_code == 200
    )


def test_rate_limit_returns_429_past_the_cap(monkeypatch) -> None:
    monkeypatch.setenv("LEAD_MAGNET_RATE_PER_HOUR", "2")
    get_settings.cache_clear()
    client = _app(rate_limit)

    assert client.post("/t").status_code == 200
    assert client.post("/t").status_code == 200
    assert client.post("/t").status_code == 429


def test_window_resets() -> None:
    limiter = FixedWindowRateLimiter(limit=1, window_s=60)
    assert limiter.check("ip", now=0.0) is True
    assert limiter.check("ip", now=30.0) is False
    assert limiter.check("ip", now=61.0) is True


def test_limit_is_per_ip() -> None:
    limiter = FixedWindowRateLimiter(limit=1, window_s=60)
    assert limiter.check("a", now=0.0) is True
    assert limiter.check("b", now=0.0) is True
    assert limiter.check("a", now=0.0) is False


def _request_with(xff: str | None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": ("172.18.0.2", 1234)})


def test_client_ip_takes_the_last_forwarded_entry() -> None:
    """Caddy is a sibling container, so `request.client.host` is always
    Caddy. Caddy appends the real peer, so the rightmost value is the
    trustworthy one — the leftmost is attacker-controlled.
    """
    assert client_ip(_request_with("1.2.3.4, 203.0.113.9")) == "203.0.113.9"
    # A forged leftmost value must not let one caller impersonate many.
    assert client_ip(_request_with("spoofed, 203.0.113.9")) == "203.0.113.9"


def test_client_ip_falls_back_to_the_peer() -> None:
    assert client_ip(_request_with(None)) == "172.18.0.2"
