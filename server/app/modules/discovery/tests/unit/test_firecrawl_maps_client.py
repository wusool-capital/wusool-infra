"""`FirecrawlMapsClient.find_potential_sellers` — the Firecrawl SDK call
itself isn't exercised here (mocked), but the exclude-filtering-before-limit
behavior is real, end-to-end through the client's own method.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.discovery.providers.firecrawl.client import FirecrawlMapsClient


def _scrape_result(businesses: list[dict], links: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(json={"businesses": businesses}, links=links or [])


async def test_excludes_a_matching_lead_before_applying_the_limit() -> None:
    client = FirecrawlMapsClient(api_key="test-key")
    client._client.scrape = AsyncMock(
        return_value=_scrape_result(
            [
                {"name": "Acme Clinics", "category": "Healthcare"},
                {"name": "Acme Construction", "category": "Construction"},
                {"name": "Acme Wellness", "category": "Healthcare"},
            ]
        )
    )

    leads = await client.find_potential_sellers(
        industry="Healthcare", geography="UAE", limit=2, exclude_terms=("construction",)
    )

    assert [lead.name for lead in leads] == ["Acme Clinics", "Acme Wellness"]


async def test_limit_is_applied_after_filtering_not_before() -> None:
    """An excluded lead must not consume a slot a qualifying one could have
    filled — regression coverage for filtering-then-slicing order."""
    client = FirecrawlMapsClient(api_key="test-key")
    client._client.scrape = AsyncMock(
        return_value=_scrape_result(
            [
                {"name": "Acme Construction", "category": "Construction"},
                {"name": "Acme Clinics", "category": "Healthcare"},
                {"name": "Acme Wellness", "category": "Healthcare"},
            ]
        )
    )

    leads = await client.find_potential_sellers(
        industry="Healthcare", geography="UAE", limit=2, exclude_terms=("construction",)
    )

    assert len(leads) == 2
    assert all(lead.category == "Healthcare" for lead in leads)


async def test_no_exclude_terms_returns_everything_up_to_the_limit() -> None:
    client = FirecrawlMapsClient(api_key="test-key")
    client._client.scrape = AsyncMock(
        return_value=_scrape_result(
            [{"name": "Acme Clinics", "category": "Healthcare"}, {"name": "Acme Construction"}]
        )
    )

    leads = await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert len(leads) == 2


async def test_logs_how_many_leads_were_excluded(caplog) -> None:
    """ "Why did I get fewer leads than expected" must be answerable from
    logs alone — a silent filter isn't debuggable."""
    client = FirecrawlMapsClient(api_key="test-key")
    client._client.scrape = AsyncMock(
        return_value=_scrape_result(
            [
                {"name": "Acme Clinics", "category": "Healthcare"},
                {"name": "Acme Construction", "category": "Construction"},
            ]
        )
    )

    with caplog.at_level("INFO"):
        await client.find_potential_sellers(
            industry="Healthcare", geography="UAE", limit=5, exclude_terms=("construction",)
        )

    assert "discovery_leads_excluded" in caplog.text
    assert "excluded=1" in caplog.text


async def test_does_not_log_when_nothing_was_excluded(caplog) -> None:
    client = FirecrawlMapsClient(api_key="test-key")
    client._client.scrape = AsyncMock(
        return_value=_scrape_result([{"name": "Acme Clinics", "category": "Healthcare"}])
    )

    with caplog.at_level("INFO"):
        await client.find_potential_sellers(
            industry="Healthcare", geography="UAE", limit=5, exclude_terms=("construction",)
        )

    assert "discovery_leads_excluded" not in caplog.text


async def test_logs_the_query_and_result_on_every_successful_run(caplog) -> None:
    """A clean, non-excluded run previously left zero log trace of what
    query ran or what it found — the only prior log lines fired on
    failure or when an exclusion removed something."""
    client = FirecrawlMapsClient(api_key="test-key")
    client._client.scrape = AsyncMock(
        return_value=_scrape_result([{"name": "Acme Clinics", "category": "Healthcare"}])
    )

    with caplog.at_level("INFO"):
        await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert "discovery_maps_search_completed" in caplog.text
    assert "query=Healthcare companies UAE" in caplog.text
    assert "businesses_found=1" in caplog.text


async def test_logs_zero_resolved_place_links_when_none_matched(caplog) -> None:
    client = FirecrawlMapsClient(api_key="test-key")
    client._client.scrape = AsyncMock(
        return_value=_scrape_result([{"name": "Acme Clinics", "category": "Healthcare"}])
    )

    with caplog.at_level("INFO"):
        await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert "resolved_place_links=0" in caplog.text


async def test_logs_resolved_place_links_when_matched(caplog) -> None:
    client = FirecrawlMapsClient(api_key="test-key")
    client._client.scrape = AsyncMock(
        return_value=_scrape_result(
            [{"name": "Acme Clinics", "category": "Healthcare"}],
            links=["https://www.google.com/maps/place/Acme+Clinics/@40.7,-74.0,15z"],
        )
    )

    with caplog.at_level("INFO"):
        await client.find_potential_sellers(industry="Healthcare", geography="UAE", limit=5)

    assert "resolved_place_links=1" in caplog.text
