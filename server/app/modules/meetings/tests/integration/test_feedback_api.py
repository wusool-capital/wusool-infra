"""POST /desktop/feedback -- no DB involved, so this runs as a plain unit
test against a bare app built from just the feedback router, matching
`test_verify_api.py`'s pattern. A `_FakeMailer` replaces `feedback_mailer`
via `dependency_overrides` so no real SES call is ever made.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.meetings.api.dependencies import feedback_mailer
from app.modules.meetings.api.feedback import _limiter
from app.modules.meetings.api.feedback import router as feedback_router
from app.modules.meetings.config import get_settings
from app.modules.utilities.api.handlers import register_exception_handlers

_VALID_KEY = "test-desktop-api-key"  # matches conftest.py's DESKTOP_API_KEY default

_VALID_PAYLOAD = {
    "message": "Recording button was unresponsive after resuming from sleep.",
    "category": "bug",
    "install_id": "install-abc-123",
    "app_version": "0.4.8",
    "platform": "macos 15.6 (aarch64)",
}


class _FakeMailer:
    def __init__(self, *, raise_error: bool = False) -> None:
        self.raise_error = raise_error
        self.calls: list[dict] = []

    async def send(self, *, to: str, from_addr: str, subject: str, body: str) -> None:
        if self.raise_error:
            raise RuntimeError("ses is down")
        self.calls.append({"to": to, "from_addr": from_addr, "subject": subject, "body": body})


def _make_client(mailer: _FakeMailer | None = None) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(feedback_router)
    if mailer is not None:
        app.dependency_overrides[feedback_mailer] = lambda: mailer
    return TestClient(app)


@pytest.fixture(autouse=True)
def _configured_delivery(monkeypatch: pytest.MonkeyPatch):
    """Feedback delivery is optional-config by design (§ config.py), so
    every test that isn't specifically exercising the unconfigured case
    must configure it itself -- get_settings() is lru_cache'd, so clear it
    on both sides of the test."""
    monkeypatch.setenv("FEEDBACK_EMAIL_TO", "team@example.com")
    monkeypatch.setenv("FEEDBACK_EMAIL_FROM", "scribe@example.com")
    get_settings.cache_clear()
    _limiter._hits.clear()
    yield
    get_settings.cache_clear()
    _limiter._hits.clear()


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_VALID_KEY}"}


def test_missing_authorization_header_is_rejected() -> None:
    response = _make_client(_FakeMailer()).post("/desktop/feedback", json=_VALID_PAYLOAD)
    assert response.status_code == 401


def test_wrong_key_is_rejected() -> None:
    response = _make_client(_FakeMailer()).post(
        "/desktop/feedback", json=_VALID_PAYLOAD, headers={"Authorization": "Bearer wrong-key"}
    )
    assert response.status_code == 401


def test_happy_path_sends_to_the_configured_address() -> None:
    mailer = _FakeMailer()
    response = _make_client(mailer).post(
        "/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers()
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert len(mailer.calls) == 1
    call = mailer.calls[0]
    assert call["to"] == "team@example.com"
    assert call["from_addr"] == "scribe@example.com"
    assert call["subject"]
    assert call["body"]


def test_whitespace_only_message_is_rejected() -> None:
    payload = {**_VALID_PAYLOAD, "message": "   "}
    response = _make_client(_FakeMailer()).post(
        "/desktop/feedback", json=payload, headers=_headers()
    )
    assert response.status_code == 422


def test_unknown_category_is_rejected() -> None:
    payload = {**_VALID_PAYLOAD, "category": "not-a-real-category"}
    response = _make_client(_FakeMailer()).post(
        "/desktop/feedback", json=payload, headers=_headers()
    )
    assert response.status_code == 422


def test_missing_install_id_is_rejected() -> None:
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "install_id"}
    response = _make_client(_FakeMailer()).post(
        "/desktop/feedback", json=payload, headers=_headers()
    )
    assert response.status_code == 422


def test_delivery_unconfigured_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDBACK_EMAIL_TO", "")
    get_settings.cache_clear()
    response = _make_client(_FakeMailer()).post(
        "/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers()
    )
    assert response.status_code == 503


def test_ses_delivery_failure_returns_502() -> None:
    mailer = _FakeMailer(raise_error=True)
    response = _make_client(mailer).post(
        "/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers()
    )
    assert response.status_code == 502


def test_rate_limit_blocks_the_sixth_submission_for_the_same_install() -> None:
    client = _make_client(_FakeMailer())
    for _ in range(5):
        response = client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())
        assert response.status_code == 200

    sixth = client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())
    assert sixth.status_code == 429


def test_rate_limit_is_scoped_per_install_id() -> None:
    client = _make_client(_FakeMailer())
    for _ in range(5):
        client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())

    other_install = {**_VALID_PAYLOAD, "install_id": "a-different-install"}
    response = client.post("/desktop/feedback", json=other_install, headers=_headers())
    assert response.status_code == 200
