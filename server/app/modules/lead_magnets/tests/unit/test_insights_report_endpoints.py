"""`/reports/*`: the preview never carries the gated rest, the unlock and a
returning reader get the whole report, and the Sanity webhook is signed.

No database: the session, ledger and Attio completion are faked at the
composition-root seams the endpoints import, as `test_api_endpoints.py`
explains for the module as a whole.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.lead_magnets.api import dependencies as deps
from app.modules.lead_magnets.api.insights_report import endpoints
from app.modules.lead_magnets.domain.insights_report.report import ReportDocument
from app.modules.lead_magnets.domain.shared.tool_run import ToolRunRecord

_REST = "GATED-REST-OF-THE-REPORT"
_REPORT = ReportDocument(
    slug="buyouts-in-the-gcc",
    title="Buyouts in the GCC",
    html="".join(f"<p>part {n} " + "word " * 50 + "</p>" for n in range(3)) + f"<p>{_REST}</p>",
    excerpt="E",
)
_OTHER = ReportDocument(slug="other-report", title="Other", html=_REPORT.html, excerpt="E")
_SECRET = "s3cret"


@dataclass
class _Settings:
    lead_magnet_sanity_project_id: str = "proj"
    lead_magnet_sanity_webhook_secret: str = _SECRET
    lead_magnet_webflow_api_token: str = "token"
    lead_magnet_allowed_origins: str = ""
    lead_magnet_rate_per_hour: int = 20
    lead_magnet_report_reads_per_hour: int = 300


@dataclass
class _World:
    settings: _Settings = field(default_factory=_Settings)
    recorded: list[dict] = field(default_factory=list)
    completed: list[UUID] = field(default_factory=list)
    runs: dict[UUID, ToolRunRecord] = field(default_factory=dict)
    synced: list[tuple[str | None, str | None]] = field(default_factory=list)


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
        async def sync(self, *, slug, previous_slug, featured_changed):
            world.synced.append((slug, previous_slug, featured_changed))

    async def fake_completion(run_id: UUID) -> None:
        world.completed.append(run_id)

    source = _Source(world)
    monkeypatch.setattr(endpoints, "get_settings", lambda: world.settings)
    monkeypatch.setattr(deps, "get_settings", lambda: world.settings)
    monkeypatch.setattr(endpoints, "build_report_source", lambda: source)
    monkeypatch.setattr(endpoints, "build_report_sync", lambda: _Sync())
    monkeypatch.setattr(endpoints, "build_submission_service", lambda session: _Service())
    monkeypatch.setattr(endpoints, "build_tool_runs", lambda session: _ToolRuns())
    monkeypatch.setattr(endpoints, "run_completion", fake_completion)
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


def test_unlock_returns_the_whole_report_and_remembers_the_reader(client, world) -> None:
    response = client.post(
        "/reports/buyouts-in-the-gcc/unlock",
        json={
            "submission_id": "sub-1",
            "name": "Dana",
            "email": "dana@gmail.com",
            "company": "Acme",
        },
    )

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
    assert len(world.completed) == 1


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
def test_unlock_accepts_real_addresses_including_free_mail(client, email: str) -> None:
    response = client.post(
        "/reports/buyouts-in-the-gcc/unlock",
        json={"submission_id": "s", "name": "D", "email": email, "company": "A"},
    )
    assert response.status_code == 200


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
    timestamp = "1791210000000"
    digest = hmac.new(_SECRET.encode(), timestamp.encode() + b"." + body, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return {"sanity-webhook-signature": f"t={timestamp},v1={signature}"}


def test_the_sanity_webhook_syncs_only_when_signed(client, world) -> None:
    body = json.dumps(
        {"slug": "new-slug", "previousSlug": "old-slug", "featuredChanged": True}
    ).encode()

    unsigned = client.post("/reports/webhooks/sanity", content=body)
    signed = client.post("/reports/webhooks/sanity", content=body, headers=_signed(body))

    assert unsigned.status_code == 401
    assert signed.status_code == 204
    assert world.synced == [("new-slug", "old-slug", True)]


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
