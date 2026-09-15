"""POST /desktop/feedback against a real database (`db_session`, rolled
back at teardown) plus a `_FakeMailer` overriding `feedback_mailer` so no
real SES call is ever made. Skips cleanly when no database is reachable
(see `conftest.py`).

Uses `httpx.AsyncClient` + `ASGITransport`, not Starlette's `TestClient`:
`TestClient` runs the ASGI app through `anyio`'s `BlockingPortal`, which
executes in a *different* event loop than the one that created
`db_session` -- asyncpg's connection is loop-bound, so a request through
`TestClient` raises "Future attached to a different loop" the moment the
endpoint touches the session. `AsyncClient` calls the app in-process, on
this same test's event loop, avoiding the boundary entirely.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.models import FeedbackSubmission
from app.modules.meetings.api.dependencies import feedback_mailer, get_session
from app.modules.meetings.api.feedback import _install_limiter, _ip_limiter
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

    async def send(self, *, to: list[str], from_addr: str, subject: str, body: str) -> None:
        if self.raise_error:
            raise RuntimeError("ses is down")
        self.calls.append({"to": to, "from_addr": from_addr, "subject": subject, "body": body})


def _make_client(db_session, mailer: _FakeMailer) -> AsyncClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(feedback_router)
    app.dependency_overrides[feedback_mailer] = lambda: mailer

    async def _override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _only_row(db_session) -> FeedbackSubmission:
    result = await db_session.execute(select(FeedbackSubmission))
    return result.scalar_one()


@pytest.fixture(autouse=True)
def _configured_delivery(monkeypatch: pytest.MonkeyPatch):
    """Most tests want delivery configured; the two that don't override it
    themselves. `get_settings()` is `lru_cache`'d, so clear it on both
    sides of the test."""
    monkeypatch.setenv("FEEDBACK_EMAIL_TO", "team-a@example.com team-b@example.com")
    monkeypatch.setenv("FEEDBACK_EMAIL_FROM", "scribe@example.com")
    get_settings.cache_clear()
    _install_limiter._hits.clear()
    _ip_limiter._hits.clear()
    yield
    get_settings.cache_clear()
    _install_limiter._hits.clear()
    _ip_limiter._hits.clear()


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_VALID_KEY}"}


async def test_missing_authorization_header_is_rejected(db_session) -> None:
    async with _make_client(db_session, _FakeMailer()) as client:
        response = await client.post("/desktop/feedback", json=_VALID_PAYLOAD)
    assert response.status_code == 401


async def test_wrong_key_is_rejected(db_session) -> None:
    async with _make_client(db_session, _FakeMailer()) as client:
        response = await client.post(
            "/desktop/feedback",
            json=_VALID_PAYLOAD,
            headers={"Authorization": "Bearer wrong-key"},
        )
    assert response.status_code == 401


async def test_happy_path_persists_the_row_and_schedules_email_to_every_recipient(
    db_session,
) -> None:
    """The row's `email_sent` flip is deliberately NOT asserted here: the
    background task (`bootstrap.send_feedback_email`) marks it via its OWN
    session/connection, invisible to `db_session`'s still-open transaction
    -- the same reason `test_role_lookup.py`'s fixture exists in the first
    place. That write path is covered directly by
    `test_feedback_repository.py::test_mark_email_sent_sets_both_columns`
    and by `test_bootstrap_feedback_email.py`'s orchestration tests. This
    test only asserts what's actually observable through this connection:
    the row exists with the right fields, and the background task ran
    (proven by the fake mailer receiving the call).
    """
    mailer = _FakeMailer()
    async with _make_client(db_session, mailer) as client:
        response = await client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    row = await _only_row(db_session)
    assert row.category == "bug"
    assert row.message == _VALID_PAYLOAD["message"]
    assert row.install_id == "install-abc-123"

    assert len(mailer.calls) == 1
    call = mailer.calls[0]
    assert call["to"] == ["team-a@example.com", "team-b@example.com"]
    assert call["from_addr"] == "scribe@example.com"
    assert call["subject"]
    assert call["body"]


async def test_whitespace_only_message_is_rejected(db_session) -> None:
    payload = {**_VALID_PAYLOAD, "message": "   "}
    async with _make_client(db_session, _FakeMailer()) as client:
        response = await client.post("/desktop/feedback", json=payload, headers=_headers())
    assert response.status_code == 422


async def test_unknown_category_is_rejected(db_session) -> None:
    payload = {**_VALID_PAYLOAD, "category": "not-a-real-category"}
    async with _make_client(db_session, _FakeMailer()) as client:
        response = await client.post("/desktop/feedback", json=payload, headers=_headers())
    assert response.status_code == 422


async def test_missing_install_id_is_rejected(db_session) -> None:
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "install_id"}
    async with _make_client(db_session, _FakeMailer()) as client:
        response = await client.post("/desktop/feedback", json=payload, headers=_headers())
    assert response.status_code == 422


async def test_unconfigured_delivery_still_persists_and_skips_email(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FEEDBACK_EMAIL_TO", "")
    get_settings.cache_clear()
    mailer = _FakeMailer()

    async with _make_client(db_session, mailer) as client:
        response = await client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())

    assert response.status_code == 200
    row = await _only_row(db_session)
    assert row.email_sent is False
    assert mailer.calls == []


async def test_whitespace_only_email_to_is_treated_as_unconfigured(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FEEDBACK_EMAIL_TO", "   ")
    get_settings.cache_clear()
    mailer = _FakeMailer()

    async with _make_client(db_session, mailer) as client:
        response = await client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())

    assert response.status_code == 200
    assert mailer.calls == []


async def test_email_failure_in_the_background_task_still_returns_200(db_session) -> None:
    """The exception raised inside the scheduled background task must not
    surface as a 500 -- `submit_feedback` itself never awaits the send, so
    there's nothing in the request path left to fail. Whether
    `mark_email_sent` correctly gets skipped on a raised send is asserted
    directly, without a background task or a second DB connection, in
    `test_bootstrap_feedback_email.py`.
    """
    mailer = _FakeMailer(raise_error=True)
    async with _make_client(db_session, mailer) as client:
        response = await client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())

    assert response.status_code == 200
    row = await _only_row(db_session)
    assert row.category == "bug"


async def test_rate_limit_blocks_the_sixth_submission_for_the_same_install(db_session) -> None:
    async with _make_client(db_session, _FakeMailer()) as client:
        for _ in range(5):
            response = await client.post(
                "/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers()
            )
            assert response.status_code == 200

        sixth = await client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())
    assert sixth.status_code == 429


async def test_rate_limit_is_scoped_per_install_id(db_session) -> None:
    async with _make_client(db_session, _FakeMailer()) as client:
        for _ in range(5):
            await client.post("/desktop/feedback", json=_VALID_PAYLOAD, headers=_headers())

        other_install = {**_VALID_PAYLOAD, "install_id": "a-different-install"}
        response = await client.post("/desktop/feedback", json=other_install, headers=_headers())
    assert response.status_code == 200


async def test_rotating_install_id_cannot_bypass_the_rate_limit(db_session) -> None:
    """A caller holding the shared DESKTOP_API_KEY could otherwise defeat
    an install_id-only limit by sending a fresh id on every request --
    `_ip_limiter` is what actually bounds this, since every request here
    comes from the same client/IP regardless of install_id."""
    async with _make_client(db_session, _FakeMailer()) as client:
        for i in range(20):
            payload = {**_VALID_PAYLOAD, "install_id": f"install-{i}"}
            response = await client.post("/desktop/feedback", json=payload, headers=_headers())
            assert response.status_code == 200

        payload = {**_VALID_PAYLOAD, "install_id": "install-20-never-seen-before"}
        response = await client.post("/desktop/feedback", json=payload, headers=_headers())
    assert response.status_code == 429
