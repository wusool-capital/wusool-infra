"""`GooglePlacesClient.find_potential_sellers` — no real network call:
`aiohttp.ClientSession` is monkeypatched via the shared `tests.aiohttp_fakes`
helper (`get` fakes the geocode call, `post` fakes the places search).
Covers the geocode -> restrict -> country-filter -> map -> exclude -> limit
pipeline; exclude-before-limit ordering and the log lines are ported from
the old Firecrawl client's own suite, since that behavior is this module's,
not the vendor's.
"""

from types import SimpleNamespace

import aiohttp

from app.modules.discovery.providers.google_places.client import (
    _REQUEST_TIMEOUT,
    GooglePlacesClient,
)
from tests.aiohttp_fakes import FakeAiohttpResponse, FakeAiohttpSession, patch_aiohttp_session


def _geocode_ok(*, country: str = "United Arab Emirates") -> FakeAiohttpResponse:
    return FakeAiohttpResponse(
        200,
        {
            "status": "OK",
            "results": [
                {
                    "geometry": {
                        "viewport": {
                            "northeast": {"lat": 25.4, "lng": 55.6},
                            "southwest": {"lat": 24.8, "lng": 54.9},
                        }
                    },
                    "address_components": [{"long_name": country, "types": ["country"]}],
                }
            ],
        },
    )


def _geocode_zero_results() -> FakeAiohttpResponse:
    return FakeAiohttpResponse(200, {"status": "ZERO_RESULTS", "results": []})


def _places(businesses: list[dict]) -> FakeAiohttpResponse:
    return FakeAiohttpResponse(200, {"places": businesses})


def _business(
    name: str,
    *,
    category: str | None = None,
    country: str = "United Arab Emirates",
    website: str | None = None,
    types: list[str] | None = None,
    maps_uri: str | None = "https://maps.google.com/?cid=1",
) -> dict:
    business: dict = {"displayName": {"text": name}}
    if category:
        business["primaryTypeDisplayName"] = {"text": category}
    if maps_uri:
        business["googleMapsUri"] = maps_uri
    if website:
        business["websiteUri"] = website
    if types:
        business["types"] = types
    business["addressComponents"] = [{"longText": country, "types": ["country"]}]
    return business


async def test_excludes_a_matching_lead_before_applying_the_limit(monkeypatch) -> None:
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(
            get=_geocode_ok(),
            post=_places(
                [
                    _business("Acme Clinics", category="Healthcare"),
                    _business("Acme Construction", category="Construction"),
                    _business("Acme Wellness", category="Healthcare"),
                ]
            ),
        ),
    )
    client = GooglePlacesClient(api_key="test-key")

    leads = await client.find_potential_sellers(
        industry="Healthcare", geography="UAE", limit=2, exclude_terms=("construction",)
    )

    assert [lead.name for lead in leads] == ["Acme Clinics", "Acme Wellness"]


async def test_limit_is_applied_after_filtering_not_before(monkeypatch) -> None:
    """An excluded lead must not consume a slot a qualifying one could have
    filled — regression coverage for filtering-then-slicing order."""
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(
            get=_geocode_ok(),
            post=_places(
                [
                    _business("Acme Construction", category="Construction"),
                    _business("Acme Clinics", category="Healthcare"),
                    _business("Acme Wellness", category="Healthcare"),
                ]
            ),
        ),
    )
    client = GooglePlacesClient(api_key="test-key")

    leads = await client.find_potential_sellers(
        industry="Healthcare", geography="UAE", limit=2, exclude_terms=("construction",)
    )

    assert len(leads) == 2
    assert all(lead.category == "Healthcare" for lead in leads)


async def test_no_exclude_terms_returns_everything_up_to_the_limit(monkeypatch) -> None:
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(
            get=_geocode_ok(),
            post=_places([_business("Acme Clinics"), _business("Acme Construction")]),
        ),
    )
    client = GooglePlacesClient(api_key="test-key")

    leads = await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert len(leads) == 2


async def test_logs_how_many_leads_were_excluded(monkeypatch, caplog) -> None:
    """ "Why did I get fewer leads than expected" must be answerable from
    logs alone — a silent filter isn't debuggable."""
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(
            get=_geocode_ok(),
            post=_places(
                [
                    _business("Acme Clinics", category="Healthcare"),
                    _business("Acme Construction", category="Construction"),
                ]
            ),
        ),
    )
    client = GooglePlacesClient(api_key="test-key")

    with caplog.at_level("INFO"):
        await client.find_potential_sellers(
            industry="Healthcare", geography="UAE", limit=5, exclude_terms=("construction",)
        )

    assert "discovery_leads_excluded" in caplog.text
    assert "excluded=1" in caplog.text


async def test_does_not_log_when_nothing_was_excluded(monkeypatch, caplog) -> None:
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(get=_geocode_ok(), post=_places([_business("Acme Clinics")])),
    )
    client = GooglePlacesClient(api_key="test-key")

    with caplog.at_level("INFO"):
        await client.find_potential_sellers(
            industry="Healthcare", geography="UAE", limit=5, exclude_terms=("construction",)
        )

    assert "discovery_leads_excluded" not in caplog.text


async def test_a_geocoded_run_restricts_the_search_to_the_viewport(monkeypatch) -> None:
    captured: dict = {}

    class _CapturingSession(FakeAiohttpSession):
        def post(self, url: str, json: dict, headers: dict) -> FakeAiohttpResponse:
            captured["body"] = json
            return super().post(url, json=json, headers=headers)

    patch_aiohttp_session(
        monkeypatch,
        _CapturingSession(get=_geocode_ok(), post=_places([_business("Acme Clinics")])),
    )
    client = GooglePlacesClient(api_key="test-key")

    await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert "locationRestriction" in captured["body"]
    assert captured["body"]["locationRestriction"]["rectangle"] == {
        "low": {"latitude": 24.8, "longitude": 54.9},
        "high": {"latitude": 25.4, "longitude": 55.6},
    }
    # `geography` stays in the query text even when restricted —
    # `locationRestriction` narrows a categorical search, it doesn't
    # replace the text hint.
    assert captured["body"]["textQuery"] == "Healthcare companies UAE"


async def test_empty_geography_falls_back_to_a_text_only_search(monkeypatch) -> None:
    """No geocode call should even matter here — an empty `geography` must
    short-circuit before ever reaching the network."""
    captured: dict = {}

    class _CapturingSession(FakeAiohttpSession):
        def post(self, url: str, json: dict, headers: dict) -> FakeAiohttpResponse:
            captured["body"] = json
            return super().post(url, json=json, headers=headers)

    patch_aiohttp_session(
        monkeypatch,
        _CapturingSession(post=_places([_business("Acme Clinics")])),
    )
    client = GooglePlacesClient(api_key="test-key")

    leads = await client.find_potential_sellers(industry="Healthcare", geography="", limit=5)

    assert len(leads) == 1
    assert "locationRestriction" not in captured["body"]
    assert captured["body"]["textQuery"] == "Healthcare companies"


async def test_zero_results_geocode_falls_back_to_a_text_only_search(monkeypatch) -> None:
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(get=_geocode_zero_results(), post=_places([_business("Acme Clinics")])),
    )
    client = GooglePlacesClient(api_key="test-key")

    leads = await client.find_potential_sellers(industry="Healthcare", geography="Nowhere", limit=5)

    assert len(leads) == 1


async def test_an_out_of_country_place_is_dropped_and_logged(monkeypatch, caplog) -> None:
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(
            get=_geocode_ok(country="United Arab Emirates"),
            post=_places(
                [
                    _business("Acme UAE", country="United Arab Emirates"),
                    _business("Acme USA", country="United States"),
                ]
            ),
        ),
    )
    client = GooglePlacesClient(api_key="test-key")

    with caplog.at_level("INFO"):
        leads = await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert [lead.name for lead in leads] == ["Acme UAE"]
    assert "discovery_leads_out_of_country" in caplog.text
    assert "dropped=1" in caplog.text


async def test_a_place_with_no_country_component_is_kept() -> None:
    """The country check can't tell either way, so it must not drop a lead
    it can't actually evaluate."""
    from app.modules.discovery.providers.google_places.client import GooglePlacesClient
    from app.modules.discovery.providers.google_places.schemas import LocalizedText, Place

    place = Place(displayName=LocalizedText(text="Acme Co"), addressComponents=[])

    lead = GooglePlacesClient._to_lead(place, "Healthcare companies")

    assert lead is not None
    assert lead.country is None


async def test_a_place_with_no_country_component_is_logged_as_unverified(
    monkeypatch, caplog
) -> None:
    """Kept-but-unevaluated must be distinguishable in logs from
    verified-in-country — silently keeping it would hide the one case where
    the geography guarantee doesn't actually hold."""
    business = _business("Acme Co")
    business["addressComponents"] = []  # Places omitted them for this result
    patch_aiohttp_session(
        monkeypatch, FakeAiohttpSession(get=_geocode_ok(), post=_places([business]))
    )
    client = GooglePlacesClient(api_key="test-key")

    with caplog.at_level("INFO"):
        leads = await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert len(leads) == 1
    assert "discovery_leads_unverified_country" in caplog.text
    assert "kept_without_verification=1" in caplog.text


async def test_a_place_with_no_display_name_is_skipped(monkeypatch) -> None:
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(
            get=_geocode_ok(),
            post=FakeAiohttpResponse(200, {"places": [{"formattedAddress": "no name here"}]}),
        ),
    )
    client = GooglePlacesClient(api_key="test-key")

    leads = await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert leads == []


async def test_website_and_country_reach_the_discovered_lead(monkeypatch) -> None:
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(
            get=_geocode_ok(),
            post=_places([_business("Acme Clinics", website="https://acme.example.com")]),
        ),
    )
    client = GooglePlacesClient(api_key="test-key")

    leads = await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert leads[0].website == "https://acme.example.com"
    assert leads[0].country == "United Arab Emirates"


async def test_a_search_transport_failure_returns_no_leads(monkeypatch, caplog) -> None:
    patch_aiohttp_session(
        monkeypatch, FakeAiohttpSession(get=_geocode_ok(), post=ConnectionError("boom"))
    )
    client = GooglePlacesClient(api_key="test-key")

    with caplog.at_level("WARNING"):
        leads = await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert leads == []
    assert "discovery_places_search_error" in caplog.text


async def test_a_geocode_transport_failure_falls_back_to_text_only_search(
    monkeypatch, caplog
) -> None:
    """The Geocoding API only supports `key=` as a query param (no header
    auth like Places' own `X-Goog-Api-Key`) — a transport failure here must
    degrade to the unrestricted fallback, same as `ZERO_RESULTS`."""
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(get=ConnectionError("boom"), post=_places([_business("Acme Clinics")])),
    )
    client = GooglePlacesClient(api_key="test-key")

    with caplog.at_level("WARNING"):
        leads = await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert len(leads) == 1
    assert "discovery_geocode_error" in caplog.text


async def test_a_geocode_response_error_never_logs_the_api_key(monkeypatch, caplog) -> None:
    """aiohttp's own `ClientResponseError`/`ContentTypeError` embeds the
    full request URL — including this GET's `key=` query param — in its
    `str()`. Logging that exception with `exc_info=True` (or any use of
    `str(exc)`) would leak the API key into application logs; the log line
    must carry only the exception's type name."""
    secret_key = "s3cr3t-google-places-key"
    leaking_error = aiohttp.ClientResponseError(
        request_info=SimpleNamespace(
            real_url=f"https://maps.googleapis.com/maps/api/geocode/json?key={secret_key}"
        ),
        history=(),
        status=200,
        message="Attempt to decode JSON with unexpected mimetype: text/html",
    )
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(get=leaking_error, post=_places([_business("Acme Clinics")])),
    )
    client = GooglePlacesClient(api_key=secret_key)

    with caplog.at_level("WARNING"):
        await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert "discovery_geocode_error" in caplog.text
    assert secret_key not in caplog.text
    assert "error_type=ClientResponseError" in caplog.text


async def test_logs_the_query_and_result_on_every_successful_run(monkeypatch, caplog) -> None:
    """A clean run must leave a trace of what query ran and what it found —
    the only per-run "did this actually run and find N businesses" line."""
    patch_aiohttp_session(
        monkeypatch,
        FakeAiohttpSession(get=_geocode_ok(), post=_places([_business("Acme Clinics")])),
    )
    client = GooglePlacesClient(api_key="test-key")

    with caplog.at_level("INFO"):
        await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert "discovery_places_search_completed" in caplog.text
    assert "query=Healthcare companies UAE" in caplog.text
    assert "businesses_found=1" in caplog.text


def test_request_timeout_is_bounded() -> None:
    assert _REQUEST_TIMEOUT.total is not None
    assert 0 < _REQUEST_TIMEOUT.total <= 30
