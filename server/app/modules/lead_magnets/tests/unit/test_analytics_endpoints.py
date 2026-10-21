"""The analytics plumbing for the lead tools: the public config, the tracked
Book a Call redirect, and `lead_submitted`, which names a person only when the
visitor accepted tracking.

No database: sessions and the ledger are faked at the seams the endpoints
import, as `test_insights_report_endpoints.py` explains.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from app.modules.lead_magnets.api import analytics as analytics_api
from app.modules.lead_magnets.api import dependencies as deps
from app.modules.lead_magnets.api.get_started import endpoints as get_started_endpoints
from app.modules.lead_magnets.api.schemas import AnalyticsContext, UtmTags
from app.modules.lead_magnets.domain.shared.lead_event import LeadEvent

_SELLER_CALENDAR = "https://calendar.app.google/UfXxu6dBkZ8wjhnT6"
_BUYER_CALENDAR = "https://calendar.app.google/4FzN5jAf5KGQszjY7"


@dataclass
class _Settings:
    lead_magnet_report_reads_per_hour: int = 300
    lead_magnet_rate_per_hour: int = 20
    lead_magnet_allowed_origins: str = ""
    lead_magnet_posthog_api_key: str = "phc_test"
    lead_magnet_posthog_host: str = "https://eu.i.posthog.com"


@dataclass
class _World:
    settings: _Settings = field(default_factory=_Settings)
    events: list[LeadEvent] = field(default_factory=list)
    recorded: list[dict[str, object]] = field(default_factory=list)
    broken: bool = False


class _Analytics:
    is_test = True

    def __init__(self, world: _World) -> None:
        self._world = world

    async def capture_lead(self, event: LeadEvent) -> None:
        if self._world.broken:
            raise RuntimeError("analytics down")
        self._world.events.append(event)


class _Session:
    async def commit(self) -> None:
        pass


@pytest.fixture
def world(monkeypatch) -> _World:
    world = _World()

    class _Service:
        async def record(self, *, tool, payload, email, domain) -> UUID:
            world.recorded.append({"tool": tool, "payload": payload})
            return uuid4()

    async def fake_completion(run_id: UUID) -> None:
        pass

    monkeypatch.setattr(analytics_api, "get_settings", lambda: world.settings)
    monkeypatch.setattr(deps, "get_settings", lambda: world.settings)
    monkeypatch.setattr(analytics_api, "build_analytics", lambda: _Analytics(world))
    monkeypatch.setattr(get_started_endpoints, "build_submission_service", lambda s: _Service())
    monkeypatch.setattr(get_started_endpoints, "run_completion", fake_completion)
    return world


@pytest.fixture
def client(world: _World):
    app = FastAPI()
    app.include_router(analytics_api.router)
    app.include_router(get_started_endpoints.router)

    async def fake_session():
        yield _Session()

    app.dependency_overrides[deps.get_session] = fake_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_the_config_gives_a_page_what_it_needs_to_load_posthog(client) -> None:
    response = client.get("/analytics/config")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "key": "phc_test",
        "host": "https://eu.i.posthog.com",
        "assets_host": "https://eu-assets.i.posthog.com",
        "is_test": True,
    }
    assert response.headers["cache-control"] == "public, max-age=300"


def test_a_blank_key_turns_the_pages_tracking_off(client, world) -> None:
    world.settings.lead_magnet_posthog_api_key = ""

    body = client.get("/analytics/config").json()

    assert body["enabled"] is False and body["key"] == ""


@pytest.mark.parametrize(
    ("tool", "calendar"),
    [
        ("valuation", _SELLER_CALENDAR),
        ("readiness", _SELLER_CALENDAR),
        ("benchmark", _SELLER_CALENDAR),
        ("get_started", _SELLER_CALENDAR),
        ("buyer_network", _BUYER_CALENDAR),
    ],
)
def test_the_email_link_redirects_to_the_tools_calendar_and_counts_the_click(
    client, world, tool: str, calendar: str
) -> None:
    response = client.get(f"/go/book-call/{tool}?sid=abc-123", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == calendar
    assert response.headers["cache-control"] == "no-store"
    (event,) = world.events
    assert (event.event, event.tool, event.submission_id, event.source) == (
        "book_call_clicked",
        tool,
        "abc-123",
        "email",
    )
    assert event.person is None, "an email click never names anyone"


def test_the_redirect_cannot_be_pointed_anywhere_else(client, world) -> None:
    for url in (
        "/go/book-call/evil?sid=x",
        "/go/book-call/insights_report?sid=x",
        "/go/book-call/valuation?sid=x&url=https://evil.example",
    ):
        response = client.get(url, follow_redirects=False)
        assert response.headers.get("location") in (None, _SELLER_CALENDAR), url

    assert [e.tool for e in world.events] == ["valuation"], "unknown tools are rejected"


def test_a_missing_or_huge_sid_still_redirects(client, world) -> None:
    missing = client.get("/go/book-call/readiness", follow_redirects=False)
    huge = client.get(f"/go/book-call/readiness?sid={'x' * 500}", follow_redirects=False)

    assert missing.status_code == huge.status_code == 302
    assert [len(e.submission_id) for e in world.events] == [len("unknown"), 64]


def test_a_broken_analytics_client_never_blocks_the_redirect(client, world) -> None:
    world.broken = True

    response = client.get("/go/book-call/readiness?sid=abc", follow_redirects=False)

    assert response.status_code == 302 and response.headers["location"] == _SELLER_CALENDAR


async def _run(background: BackgroundTasks) -> None:
    for task in background.tasks:
        await task()


def _track(background: BackgroundTasks, analytics: AnalyticsContext | None) -> None:
    analytics_api.track_lead(
        background,
        tool="readiness",
        submission_id="sub-1",
        analytics=analytics,
        name="Dana",
        email="dana@acme.ae",
        company="Acme",
    )


async def test_a_consented_lead_names_the_person_and_links_the_visitor(world) -> None:
    background = BackgroundTasks()
    _track(background, AnalyticsContext(consent=True, visitor_id="anon-1"))
    await _run(background)

    (event,) = world.events
    assert event.event == "lead_submitted" and event.visitor_id == "anon-1"
    assert event.person is not None
    assert (event.person.name, event.person.email, event.person.company) == (
        "Dana",
        "dana@acme.ae",
        "Acme",
    )


@pytest.mark.parametrize(
    "analytics",
    [None, AnalyticsContext(), AnalyticsContext(consent=False, visitor_id="anon-1")],
)
async def test_without_consent_a_lead_is_counted_but_never_named(world, analytics) -> None:
    background = BackgroundTasks()
    _track(background, analytics)
    await _run(background)

    (event,) = world.events
    assert event.person is None and event.visitor_id is None
    assert event.submission_id == "sub-1"


def test_a_visitor_id_without_consent_is_dropped_by_the_request_model() -> None:
    context = AnalyticsContext(consent=False, visitor_id="anon-1", utm=UtmTags(source="x"))

    assert context.visitor_id is None
    assert context.utm == UtmTags(source="x"), "campaign tags are kept either way"


def _get_started(**analytics: object) -> dict[str, object]:
    body: dict[str, object] = {
        "submission_id": "page-load-1",
        "name": "Dana",
        "company": "Acme",
        "email": "dana@acme.ae",
        "geography": "UAE",
        "sector": "Retail",
        "revenue": 1000,
        "ebitda": 100,
        "years_active": 5,
        "sell_timeline": "6 months",
        "consent": True,
    }
    if analytics:
        body["analytics"] = analytics
    return body


def test_a_get_started_lead_with_consent_is_named_and_keeps_its_campaign(client, world) -> None:
    response = client.post(
        "/get-started",
        json=_get_started(
            visitor_id="anon-1", consent=True, utm={"source": "linkedin", "campaign": "gcc"}
        ),
    )

    assert response.status_code == 200
    (event,) = world.events
    assert event.person is not None and event.person.email == "dana@acme.ae"
    assert event.visitor_id == "anon-1" and event.submission_id == "page-load-1"
    stored = world.recorded[0]["payload"]
    assert isinstance(stored, dict)
    assert stored["analytics"]["utm"] == {
        "source": "linkedin",
        "medium": None,
        "campaign": "gcc",
        "term": None,
        "content": None,
    }


def test_a_get_started_lead_that_declined_is_counted_without_an_id_or_email(client, world) -> None:
    response = client.post(
        "/get-started",
        json=_get_started(visitor_id="anon-1", consent=False, utm={"source": "linkedin"}),
    )

    assert response.status_code == 200
    (event,) = world.events
    assert event.person is None and event.visitor_id is None
    stored = world.recorded[0]["payload"]
    assert isinstance(stored, dict)
    assert stored["analytics"]["visitor_id"] is None, "never stored without consent"


def test_a_lead_without_any_analytics_block_still_works(client, world) -> None:
    response = client.post("/get-started", json=_get_started())

    assert response.status_code == 200
    assert world.events[0].person is None


def test_a_broken_analytics_client_never_loses_a_lead(client, world) -> None:
    world.broken = True

    response = client.post("/get-started", json=_get_started(consent=True))

    assert response.status_code == 200
    assert len(world.recorded) == 1


@pytest.mark.parametrize(
    ("module", "tool"),
    [
        ("benchmark", "benchmark"),
        ("buyer_network", "buyer_network"),
        ("get_started", "get_started"),
        ("readiness", "readiness"),
        ("valuation", "valuation"),
    ],
)
def test_every_lead_endpoint_reports_its_own_lead(module: str, tool: str) -> None:
    """A forgotten call would silently undercount that tool in the funnel."""
    source = Path(analytics_api.__file__).parent / module / "endpoints.py"
    calls = re.findall(r'track_lead\(\s*background,\s*tool="(\w+)"', source.read_text())

    assert calls == [tool]
