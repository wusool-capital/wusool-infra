"""Apify provider coverage — schema parsing against recorded fixtures,
request shape (token only in the header, vendor timeout below ours) and
fail-soft behaviour. No real network: `aiohttp.ClientSession` is faked.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.modules.enrichment.domain.field_plans import ORGANIZATION_ENRICHABLE_FIELDS
from app.modules.enrichment.providers.apify.company import ApifyLinkedInCompanyClient
from app.modules.enrichment.providers.apify.linkedin import ApifyLinkedInClient
from tests.aiohttp_fakes import FakeAiohttpResponse, FakeAiohttpSession, patch_aiohttp_session

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "apify"
_TOKEN = "apify_api_SECRET"
_URL = "https://www.linkedin.com/in/jane-doe"


def _fixture(name: str) -> list:
    return json.loads((_FIXTURES / f"{name}.json").read_text())


def _session(monkeypatch, response: FakeAiohttpResponse | Exception) -> FakeAiohttpSession:
    session = FakeAiohttpSession(post=response)
    patch_aiohttp_session(monkeypatch, session)
    return session


async def test_profiles_parse_recorded_fixture(monkeypatch) -> None:
    _session(monkeypatch, FakeAiohttpResponse(201, _fixture("profile")))

    profiles = await ApifyLinkedInClient(_TOKEN).profiles((_URL,))

    assert len(profiles) == 1  # the item without a url/identifier is dropped
    assert profiles[0].url == _URL
    assert profiles[0].current_company == "Globex"
    # Title comes from the open-ended experience entry; `currentPosition`
    # carries only the company in the actor's sample.
    assert profiles[0].current_title == "Chief Financial Officer"
    assert profiles[0].location == "Dubai, United Arab Emirates"


async def test_posts_parse_recorded_fixture(monkeypatch) -> None:
    _session(monkeypatch, FakeAiohttpResponse(201, _fixture("posts")))

    posts = await ApifyLinkedInClient(_TOKEN).posts((_URL,), max_posts=10, posted_limit="month")

    assert len(posts) == 1  # the item without an id is dropped
    assert posts[0].external_id == "7300000000000000001"
    assert posts[0].author_name == "Jane Doe"
    assert posts[0].author_url == "https://www.linkedin.com/in/jane-doe"  # tracking query dropped
    assert posts[0].posted_at is not None
    assert posts[0].posted_at.year == 2026


async def test_token_is_only_sent_in_the_auth_header(monkeypatch) -> None:
    session = _session(monkeypatch, FakeAiohttpResponse(201, _fixture("profile")))

    await ApifyLinkedInClient(_TOKEN).profiles((_URL,))

    request = session.post_calls[0]
    assert _TOKEN not in request.url
    assert _TOKEN not in str(request.params)
    assert _TOKEN not in (request.data or "")
    assert request.headers["Authorization"] == f"Bearer {_TOKEN}"


async def test_apify_run_timeout_is_below_the_http_timeout(monkeypatch) -> None:
    session = _session(monkeypatch, FakeAiohttpResponse(201, []))

    await ApifyLinkedInClient(_TOKEN).profiles((_URL,))

    vendor_timeout = float(session.post_calls[0].params["timeout"])
    http_timeout = session.timeouts[0]
    assert http_timeout is not None and http_timeout.total is not None
    assert vendor_timeout < http_timeout.total < 60


@pytest.mark.parametrize(
    "response",
    [
        FakeAiohttpResponse(500, {}),
        FakeAiohttpResponse(408, {}),
        FakeAiohttpResponse(201, {"error": "not an array"}),
        ConnectionError("boom"),
    ],
)
async def test_failures_return_empty_without_raising(monkeypatch, response) -> None:
    _session(monkeypatch, response)

    assert await ApifyLinkedInClient(_TOKEN).profiles((_URL,)) == ()


async def test_a_malformed_item_is_skipped_not_fatal(monkeypatch) -> None:
    body = [{"linkedinUrl": _URL, "experience": "not-a-list"}, *_fixture("profile")[:1]]
    _session(monkeypatch, FakeAiohttpResponse(201, body))

    profiles = await ApifyLinkedInClient(_TOKEN).profiles((_URL,))

    assert [p.url for p in profiles] == [_URL]


async def test_no_urls_means_no_request(monkeypatch) -> None:
    session = _session(monkeypatch, FakeAiohttpResponse(201, []))

    assert await ApifyLinkedInClient(_TOKEN).profiles(()) == ()
    assert session.post_calls == []


async def test_company_maps_requested_fields_from_fixture(monkeypatch) -> None:
    _session(monkeypatch, FakeAiohttpResponse(201, _fixture("company")))

    result = await ApifyLinkedInCompanyClient(_TOKEN).lookup(
        org_name="Acme Co",
        fields=ORGANIZATION_ENRICHABLE_FIELDS,
        linkedin_url="https://www.linkedin.com/company/acme-co",
    )

    by_name = {f.field_name: f.value for f in result.fields}
    # The short name, not the formal "United States of America".
    assert by_name["hq_country"] == "United States"
    assert by_name["employee_range"] == "251-1K"
    assert by_name["description"].startswith("Acme distributes")
    # Trailing newline stripped; the expiring logo URL is never proposed.
    assert by_name["description"] == "Acme distributes food and beverage products across the GCC."
    assert "logo_url" not in by_name
    assert by_name["foundation_date"] == date(1997, 1, 1)
    assert result.website == "https://acme.example"
    assert {f.provider for f in result.fields} == {"LinkedIn (Apify)"}


async def test_company_only_returns_requested_fields(monkeypatch) -> None:
    _session(monkeypatch, FakeAiohttpResponse(201, _fixture("company")))
    only_hq = tuple(f for f in ORGANIZATION_ENRICHABLE_FIELDS if f.name == "hq_country")

    result = await ApifyLinkedInCompanyClient(_TOKEN).lookup(
        org_name="Acme Co", fields=only_hq, linkedin_url="https://www.linkedin.com/company/acme"
    )

    assert [f.field_name for f in result.fields] == ["hq_country"]


async def test_logo_is_never_proposed_even_when_requested(monkeypatch) -> None:
    _session(monkeypatch, FakeAiohttpResponse(201, _fixture("company")))
    only_logo = tuple(f for f in ORGANIZATION_ENRICHABLE_FIELDS if f.name == "logo_url")

    result = await ApifyLinkedInCompanyClient(_TOKEN).lookup(
        org_name="Acme Co", fields=only_logo, linkedin_url="https://www.linkedin.com/company/acme"
    )

    assert result.fields == []


async def test_company_without_a_linkedin_url_makes_no_request(monkeypatch) -> None:
    session = _session(monkeypatch, FakeAiohttpResponse(201, _fixture("company")))

    result = await ApifyLinkedInCompanyClient(_TOKEN).lookup(
        org_name="Acme Co", fields=ORGANIZATION_ENRICHABLE_FIELDS
    )

    assert result.fields == []
    assert session.post_calls == []


async def test_company_failure_returns_empty(monkeypatch) -> None:
    _session(monkeypatch, FakeAiohttpResponse(500, {}))

    result = await ApifyLinkedInCompanyClient(_TOKEN).lookup(
        org_name="Acme Co",
        fields=ORGANIZATION_ENRICHABLE_FIELDS,
        linkedin_url="https://www.linkedin.com/company/acme-co",
    )

    assert result.fields == []


async def test_run_logs_cost_signal_without_token(monkeypatch, caplog) -> None:
    _session(monkeypatch, FakeAiohttpResponse(201, _fixture("profile")))

    with caplog.at_level("INFO"):
        await ApifyLinkedInClient(_TOKEN).profiles((_URL,))

    assert "apify_run actor=harvestapi~linkedin-profile-scraper items=2" in caplog.text
    assert "outcome=ok" in caplog.text
    assert _TOKEN not in caplog.text


async def test_company_run_is_skipped_when_it_cannot_fill_any_requested_field(
    monkeypatch,
) -> None:
    session = _session(monkeypatch, FakeAiohttpResponse(201, _fixture("company")))
    unfillable = tuple(
        f for f in ORGANIZATION_ENRICHABLE_FIELDS if f.name in {"linkedin", "estimated_arr"}
    )
    assert unfillable  # the guard is only meaningful if these exist

    result = await ApifyLinkedInCompanyClient(_TOKEN).lookup(
        org_name="Acme Co", fields=unfillable, linkedin_url="https://www.linkedin.com/company/a"
    )

    assert result.fields == []
    assert session.post_calls == []
