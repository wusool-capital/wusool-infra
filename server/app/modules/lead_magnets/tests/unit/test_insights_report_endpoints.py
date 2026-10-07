"""`/reports/*`: the preview never carries the gated rest, only a reader who
types back the emailed code (or returns with the cookie) gets the whole
report and the PDF, and the Sanity webhook is signed.

No database: the session, ledger and Attio completion are faked at the
composition-root seams the endpoints import, as `test_api_endpoints.py`
explains for the module as a whole.
"""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.lead_magnets.api import dependencies as deps
from app.modules.lead_magnets.api.insights_report import endpoints
from app.modules.lead_magnets.application.insights_report.unlock import ReportUnlock
from app.modules.lead_magnets.domain.insights_report.report import ReportDocument
from app.modules.lead_magnets.domain.insights_report.split import split_report
from app.modules.lead_magnets.domain.shared.tool_run import ToolRunRecord
from app.modules.lead_magnets.persistence.unlock_challenges import InMemoryUnlockChallenges

_REST = "GATED-REST-OF-THE-REPORT"
_HTML = "".join(f"<p>part {n} " + "word " * 50 + "</p>" for n in range(3)) + f"<p>{_REST}</p>"
_REPORT = ReportDocument(
    slug="buyouts-in-the-gcc",
    title="Buyouts in the GCC",
    html=_HTML,
    excerpt="E",
    preview_end=len(split_report(_HTML, share=0.25)[0]),
)
_OTHER = ReportDocument(
    slug="other-report", title="Other", html=_HTML, excerpt="E", preview_end=_REPORT.preview_end
)
_SECRET = "s3cret"


@dataclass
class _Settings:
    lead_magnet_sanity_project_id: str = "proj"
    lead_magnet_sanity_webhook_secret: str = _SECRET
    lead_magnet_sanity_write_token: str = "write-token"
    lead_magnet_webflow_api_token: str = "token"
    lead_magnet_allowed_origins: str = ""
    lead_magnet_rate_per_hour: int = 20
    lead_magnet_report_reads_per_hour: int = 300
    lead_magnet_report_downloads_per_hour: int = 30
    lead_magnet_report_email_otp: bool = True


@dataclass
class _World:
    settings: _Settings = field(default_factory=_Settings)
    recorded: list[dict] = field(default_factory=list)
    completed: list[UUID] = field(default_factory=list)
    runs: dict[UUID, ToolRunRecord] = field(default_factory=dict)
    synced: list[tuple[str | None, str | None]] = field(default_factory=list)
    articles: list[tuple[str | None, str | None]] = field(default_factory=list)
    printed: list[str] = field(default_factory=list)
    emails: list[tuple[list[str], str, str]] = field(default_factory=list)


class _Source:
    def __init__(self, world: _World) -> None:
        self._world = world

    async def get(self, slug: str) -> ReportDocument | None:
        return {r.slug: r for r in (_REPORT, _OTHER)}.get(slug)

    async def refresh(self, slug: str) -> ReportDocument | None:
        return await self.get(slug)


class _Session:
    async def commit(self) -> None:
        pass


@pytest.fixture
def world(monkeypatch) -> _World:
    world = _World()

    class _Service:
        async def record(self, *, tool, payload, email, domain):
            world.recorded.append({"tool": tool, "payload": payload, "domain": domain})
            return uuid4()

    class _ToolRuns:
        async def get(self, run_id):
            return world.runs.get(run_id)

    class _Sync:
        async def sync(self, *, slug, previous_slug):
            world.synced.append((slug, previous_slug))

    class _ArticleSync:
        async def sync(self, *, slug, previous_slug):
            world.articles.append((slug, previous_slug))

    class _Renderer:
        async def pdf(self, html: str) -> bytes:
            world.printed.append(html)
            return b"%PDF-1.7 fake"

    class _Mailer:
        async def send(self, *, to, from_addr, subject, body, is_html=False):
            world.emails.append((to, subject, body))

    async def fake_completion(run_id: UUID) -> None:
        world.completed.append(run_id)

    unlock = ReportUnlock(
        challenges=InMemoryUnlockChallenges(),
        mailer=_Mailer(),
        email_from="contact@wusoolcapital.com",
        ttl_s=600,
    )

    source = _Source(world)
    monkeypatch.setattr(endpoints, "get_settings", lambda: world.settings)
    monkeypatch.setattr(deps, "get_settings", lambda: world.settings)
    monkeypatch.setattr(endpoints, "build_report_source", lambda: source)
    monkeypatch.setattr(endpoints, "build_report_sync", lambda: _Sync())
    monkeypatch.setattr(endpoints, "build_article_sync", lambda: _ArticleSync())
    monkeypatch.setattr(endpoints, "build_report_renderer", lambda: _Renderer())
    monkeypatch.setattr(endpoints, "build_submission_service", lambda session: _Service())
    monkeypatch.setattr(endpoints, "build_tool_runs", lambda session: _ToolRuns())
    monkeypatch.setattr(endpoints, "run_completion", fake_completion)
    monkeypatch.setattr(endpoints, "build_report_unlock", lambda: unlock)
    return world


@pytest.fixture
def client(world: _World):
    app = FastAPI()
    app.include_router(endpoints.router)

    async def fake_session():
        yield _Session()

    app.dependency_overrides[deps.get_session] = fake_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _sent_code(world: _World) -> str:
    _, subject, _ = world.emails[-1]
    return subject.split(" ", 1)[0]


def _unlock(client, world: _World, **form: str):
    """Both gate steps: request the code, then type it back."""
    body = {"submission_id": "s", "name": "D", "email": "dana@acme.ae", "company": "A", **form}
    sent = client.post("/reports/buyouts-in-the-gcc/unlock", json=body)
    assert sent.status_code == 200, sent.text
    return client.post(
        "/reports/buyouts-in-the-gcc/unlock/verify",
        json={"challenge_id": sent.json()["challenge_id"], "code": _sent_code(world)},
    )


def _reader_run(world: _World, slug: str) -> UUID:
    run_id = uuid4()
    world.runs[run_id] = ToolRunRecord(
        id=run_id,
        tool="insights_report",
        status="succeeded",
        attempt_count=1,
        payload={"name": "Dana", "email": "dana@acme.ae", "company": "Acme", "slug": slug},
        stage=None,
    )
    return run_id


def test_the_preview_never_carries_the_gated_rest(client) -> None:
    response = client.get("/reports/buyouts-in-the-gcc")

    assert response.status_code == 200
    body = response.json()
    assert body["locked"] is True
    assert "part 0" in body["html"]
    assert _REST not in body["html"]
    assert response.headers["cache-control"] == "no-store"


def test_unknown_or_unconfigured_reports_are_404(client, world) -> None:
    assert client.get("/reports/nope").status_code == 404
    assert client.get("/reports/Bad_Slug").status_code == 422
    world.settings.lead_magnet_sanity_project_id = ""
    assert client.get("/reports/buyouts-in-the-gcc").status_code == 404


def test_unlock_only_emails_a_code_and_records_nothing(client, world) -> None:
    response = client.post(
        "/reports/buyouts-in-the-gcc/unlock",
        json={"submission_id": "s", "name": "Dana", "email": "dana@gmail.com"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {"challenge_id"}
    assert "set-cookie" not in response.headers
    ((to, subject, body),) = world.emails
    assert to == ["dana@gmail.com"]
    assert "Buyouts in the GCC" in body and _sent_code(world) in body
    assert world.recorded == [] and world.completed == [], "no lead until the email is proven"


def test_the_right_code_returns_the_whole_report_and_remembers_the_reader(client, world) -> None:
    response = _unlock(client, world, name="Dana", email="dana@gmail.com", company="Acme")

    assert response.status_code == 200
    assert response.json()["locked"] is False
    assert _REST in response.json()["html"]
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"]
    for part in ("wusool_reader=", "HttpOnly", "Secure", "SameSite=lax", "Path=/reports"):
        assert part in cookie
    (recorded,) = world.recorded
    assert recorded["tool"] == "insights_report"
    assert recorded["domain"] is None, "free-mail is accepted, but never becomes an org domain"
    assert recorded["payload"]["slug"] == "buyouts-in-the-gcc"
    assert recorded["payload"]["email"] == "dana@gmail.com"
    assert len(world.completed) == 1


def test_with_email_otp_off_the_unlock_opens_the_report_directly(client, world) -> None:
    world.settings.lead_magnet_report_email_otp = False

    response = client.post(
        "/reports/buyouts-in-the-gcc/unlock",
        json={"submission_id": "s", "name": "Dana", "email": "dana@acme.ae", "company": "Acme"},
    )

    assert response.status_code == 200
    assert response.json()["locked"] is False and _REST in response.json()["html"]
    assert "wusool_reader=" in response.headers["set-cookie"]
    assert world.emails == [], "no code is sent"
    (recorded,) = world.recorded
    assert recorded["payload"]["slug"] == "buyouts-in-the-gcc"
    assert len(world.completed) == 1


def test_a_wrong_code_is_400_and_unlocks_nothing(client, world) -> None:
    sent = client.post(
        "/reports/buyouts-in-the-gcc/unlock",
        json={"submission_id": "s", "name": "D", "email": "dana@acme.ae"},
    )
    wrong = "000000" if _sent_code(world) != "000000" else "111111"

    response = client.post(
        "/reports/buyouts-in-the-gcc/unlock/verify",
        json={"challenge_id": sent.json()["challenge_id"], "code": wrong},
    )

    assert response.status_code == 400
    assert "set-cookie" not in response.headers
    assert world.recorded == []


def test_a_used_or_unknown_challenge_is_410(client, world) -> None:
    assert _unlock(client, world).status_code == 200
    challenge = {"challenge_id": "nope", "code": "123456"}
    response = client.post("/reports/buyouts-in-the-gcc/unlock/verify", json=challenge)
    assert response.status_code == 410


def test_a_failed_save_keeps_the_code_for_a_retry(client, world, monkeypatch) -> None:
    class _DbDown:
        async def record(self, **kwargs):
            raise RuntimeError("db down")

    body = {"submission_id": "s", "name": "D", "email": "dana@acme.ae"}
    sent = client.post("/reports/buyouts-in-the-gcc/unlock", json=body)
    verify = {"challenge_id": sent.json()["challenge_id"], "code": _sent_code(world)}

    with monkeypatch.context() as patch:
        patch.setattr(endpoints, "build_submission_service", lambda session: _DbDown())
        assert (
            client.post("/reports/buyouts-in-the-gcc/unlock/verify", json=verify).status_code == 500
        )

    retry = client.post("/reports/buyouts-in-the-gcc/unlock/verify", json=verify)
    assert retry.status_code == 200
    again = client.post("/reports/buyouts-in-the-gcc/unlock/verify", json=verify)
    assert again.status_code == 410, "spent once the lead is saved"


def test_a_failed_code_email_is_503_not_a_crash(client, world, monkeypatch) -> None:
    class _Down:
        async def send(self, **kwargs):
            raise RuntimeError("ses down")

    monkeypatch.setattr(
        endpoints,
        "build_report_unlock",
        lambda: ReportUnlock(
            challenges=InMemoryUnlockChallenges(), mailer=_Down(), email_from="x@y.z", ttl_s=600
        ),
    )
    response = client.post(
        "/reports/buyouts-in-the-gcc/unlock",
        json={"submission_id": "s", "name": "D", "email": "dana@acme.ae"},
    )
    assert response.status_code == 503


@pytest.mark.parametrize(
    "email",
    [
        "not-an-email",
        "dana@acme",
        "dana@@acme.ae",
        "dana acme@acme.ae",
        "<script>@acme.ae",
        "dana@acme..ae",
        "dana@-acme.ae",
        "@acme.ae",
        " dana@acme.ae",
    ],
)
def test_unlock_rejects_anything_that_is_not_an_email(client, email: str) -> None:
    response = client.post(
        "/reports/buyouts-in-the-gcc/unlock",
        json={"submission_id": "s", "name": "D", "email": email, "company": "A"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "email"]


@pytest.mark.parametrize(
    "email", ["dana@acme.ae", "dana.k+reports@mail.acme-group.com", "dana@gmail.com"]
)
def test_unlock_accepts_real_addresses_including_free_mail(client, world, email: str) -> None:
    assert _unlock(client, world, email=email).status_code == 200


def test_unlock_works_without_an_organisation(client, world) -> None:
    body = {"submission_id": "s", "name": "D", "email": "dana@acme.ae"}
    sent = client.post("/reports/buyouts-in-the-gcc/unlock", json=body)
    response = client.post(
        "/reports/buyouts-in-the-gcc/unlock/verify",
        json={"challenge_id": sent.json()["challenge_id"], "code": _sent_code(world)},
    )

    assert response.status_code == 200 and response.json()["locked"] is False
    assert world.recorded[0]["payload"]["company"] == ""


def test_the_pdf_is_locked_until_the_reader_unlocks(client, world) -> None:
    assert client.get("/reports/buyouts-in-the-gcc/pdf").status_code == 403
    assert world.printed == [], "a locked reader never costs a Chromium launch"

    client.cookies.set("wusool_reader", str(_reader_run(world, slug="buyouts-in-the-gcc")))
    response = client.get("/reports/buyouts-in-the-gcc/pdf")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 fake"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="buyouts-in-the-gcc.pdf"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert world.printed == [_HTML], "the whole report, not the preview"
    assert world.recorded == [], "the report this reader unlocked is already one run"


def test_a_pdf_that_times_out_in_the_queue_is_a_503_not_a_crash(client, world, monkeypatch) -> None:
    class _Busy:
        async def pdf(self, html: str) -> bytes:
            raise TimeoutError

    monkeypatch.setattr(endpoints, "build_report_renderer", lambda: _Busy())
    client.cookies.set("wusool_reader", str(_reader_run(world, slug="buyouts-in-the-gcc")))

    assert client.get("/reports/buyouts-in-the-gcc/pdf").status_code == 503


def test_a_pdf_of_another_report_records_its_own_read(client, world) -> None:
    reader = _reader_run(world, slug="buyouts-in-the-gcc")
    client.cookies.set("wusool_reader", str(reader))

    assert client.get("/reports/other-report/pdf").status_code == 200

    (recorded,) = world.recorded
    assert recorded["payload"]["submission_id"] == f"{reader}:other-report"
    assert len(world.completed) == 1


def test_a_returning_reader_skips_the_gate_and_logs_one_read_per_new_report(client, world) -> None:
    reader = _reader_run(world, slug="buyouts-in-the-gcc")
    client.cookies.set("wusool_reader", str(reader))

    same = client.get("/reports/buyouts-in-the-gcc")
    other = client.get("/reports/other-report")

    assert same.json()["locked"] is False and _REST in same.json()["html"]
    assert other.json()["locked"] is False
    (recorded,) = world.recorded
    assert recorded["payload"]["submission_id"] == f"{reader}:other-report"
    assert recorded["payload"]["email"] == "dana@acme.ae"


def test_an_unknown_reader_cookie_still_sees_the_gate(client) -> None:
    client.cookies.set("wusool_reader", "not-a-uuid")
    assert client.get("/reports/buyouts-in-the-gcc").json()["locked"] is True
    client.cookies.set("wusool_reader", str(uuid4()))
    assert client.get("/reports/buyouts-in-the-gcc").json()["locked"] is True


def _signed(body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    digest = hmac.new(_SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return {"sanity-webhook-signature": f"t={timestamp},v1={signature}"}


def test_the_sanity_webhook_syncs_only_when_signed(client, world) -> None:
    body = json.dumps({"slug": "new-slug", "previousSlug": "old-slug"}).encode()

    unsigned = client.post("/reports/webhooks/sanity", content=body)
    signed = client.post("/reports/webhooks/sanity", content=body, headers=_signed(body))

    assert unsigned.status_code == 401
    assert signed.status_code == 202
    assert world.synced == [("new-slug", "old-slug")]


def test_one_webhook_routes_reports_and_insights_articles_by_type(client, world) -> None:
    """The Free plan allows two webhooks (dev and prod), so both types share one."""
    for payload in (
        {"type": "insights", "slug": "exit-guide", "previousSlug": None},
        # An old projection still sending `featuredChanged` is ignored.
        {"type": "report", "slug": "buyouts", "previousSlug": None, "featuredChanged": True},
    ):
        body = json.dumps(payload).encode()
        assert (
            client.post("/reports/webhooks/sanity", content=body, headers=_signed(body)).status_code
            == 202
        )

    assert world.articles == [("exit-guide", None)]
    assert world.synced == [("buyouts", None)]


def test_the_sanity_webhook_is_off_until_configured(client, world) -> None:
    world.settings.lead_magnet_webflow_api_token = ""
    body = b"{}"
    assert (
        client.post("/reports/webhooks/sanity", content=body, headers=_signed(body)).status_code
        == 503
    )


def test_report_page_views_have_their_own_per_ip_limit(client, world) -> None:
    world.settings.lead_magnet_report_reads_per_hour = 2

    statuses = [client.get("/reports/buyouts-in-the-gcc").status_code for _ in range(3)]

    assert statuses == [200, 200, 429]


def test_pdf_downloads_have_their_own_per_ip_limit_apart_from_the_unlock(client, world) -> None:
    world.settings.lead_magnet_report_downloads_per_hour = 1
    client.cookies.set("wusool_reader", str(_reader_run(world, slug="buyouts-in-the-gcc")))

    downloads = [client.get("/reports/buyouts-in-the-gcc/pdf").status_code for _ in range(2)]
    unlock = client.post(
        "/reports/buyouts-in-the-gcc/unlock",
        json={"submission_id": "s", "name": "D", "email": "dana@acme.ae"},
    )

    assert downloads == [200, 429]
    assert unlock.status_code == 200, "downloading never uses up the unlock budget"
