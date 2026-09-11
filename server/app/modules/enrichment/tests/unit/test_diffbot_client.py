"""Coverage for Diffbot's field mapping — pure, no network. The client
itself (`DiffbotCompanyDataClient.lookup`) makes a real HTTP call, so it's
exercised only through this mapping function and the response schema's own
validation, not end-to-end.
"""

from datetime import date

from app.modules.enrichment.domain.field_plans import enrichable_fields_for
from app.modules.enrichment.providers.diffbot.client import (
    _REQUEST_TIMEOUT,
    _map_entity,
    _parse_founding_date,
)
from app.modules.enrichment.providers.diffbot.schemas import (
    DiffbotCountry,
    DiffbotDate,
    DiffbotLocation,
    DiffbotOrganization,
    DiffbotRevenue,
)

_ALL_SELLER_FIELDS = {f.name for f in enrichable_fields_for("seller")}


def test_map_entity_resolves_requested_fields_only() -> None:
    entity = DiffbotOrganization(
        description="A logistics company.",
        foundingDate=DiffbotDate(str="d2015-03-01"),
        nbEmployeesMin=20,
        nbEmployeesMax=49,
        revenue=DiffbotRevenue(value=5_000_000.0, currency="USD"),
        location=DiffbotLocation(country=DiffbotCountry(name="United Arab Emirates")),
        linkedInUri="https://linkedin.com/company/acme",
        origin="https://acme.com",
    )

    resolved = {
        f.field_name: f for f in _map_entity(entity, requested={"est_revenue", "foundation_date"})
    }

    assert set(resolved) == {"est_revenue", "foundation_date"}
    assert resolved["est_revenue"].value == 5_000_000.0
    assert resolved["foundation_date"].value == date(2015, 3, 1)
    assert resolved["est_revenue"].provider == "Diffbot"
    assert resolved["est_revenue"].source_url == "https://acme.com"


def test_map_entity_derives_years_active_from_founding_date() -> None:
    entity = DiffbotOrganization(foundingDate=DiffbotDate(str="d2015-03-01"))

    resolved = {f.field_name: f for f in _map_entity(entity, requested={"years_active"})}

    assert resolved["years_active"].value == date.today().year - 2015


def test_map_entity_buckets_employee_count() -> None:
    entity = DiffbotOrganization(nbEmployeesMin=20, nbEmployeesMax=49)

    resolved = {f.field_name: f for f in _map_entity(entity, requested={"employee_range"})}

    assert resolved["employee_range"].value == "11-50"


def test_map_entity_resolves_locations_and_social_profiles() -> None:
    """Diffbot's Enhance API returns `nbLocations`/`logo`/`angellistUri`/
    `facebookUri`/`twitterUri` on every call — confirmed live (Stripe
    lookup) — but they went unmapped until this pass.
    """
    entity = DiffbotOrganization(
        nbLocations=51,
        logo="https://diffbot.com/logo.png",
        angellistUri="angel.co/stripe",
        facebookUri="facebook.com/StripeHQ",
        twitterUri="twitter.com/stripe",
    )

    resolved = {
        f.field_name: f
        for f in _map_entity(
            entity, requested={"location_count", "logo_url", "angellist", "facebook", "twitter"}
        )
    }

    assert resolved["location_count"].value == 51
    assert resolved["logo_url"].value == "https://diffbot.com/logo.png"
    assert resolved["angellist"].value == "angel.co/stripe"
    assert resolved["facebook"].value == "facebook.com/StripeHQ"
    assert resolved["twitter"].value == "twitter.com/stripe"


def test_map_entity_skips_est_revenue_when_currency_is_not_usd(caplog) -> None:
    """The write path (`app/modules/attio/providers/attio/money.py`) and the
    extraction prompt both hardcode USD for `est_revenue` — proposing a
    non-USD figure as-is would silently write the wrong number. Logged so
    "why is revenue empty" is answerable from logs alone.
    """
    entity = DiffbotOrganization(revenue=DiffbotRevenue(value=5_000_000.0, currency="AED"))

    with caplog.at_level("INFO"):
        resolved = _map_entity(entity, requested={"est_revenue"})

    assert resolved == []
    assert "diffbot_est_revenue_skipped_non_usd" in caplog.text
    assert "AED" in caplog.text


def test_map_entity_resolves_est_revenue_when_currency_is_unset() -> None:
    """Diffbot doesn't always populate `currency` — absence isn't evidence
    it's non-USD, so this must still resolve (unlike a confirmed mismatch)."""
    entity = DiffbotOrganization(revenue=DiffbotRevenue(value=5_000_000.0, currency=None))

    resolved = _map_entity(entity, requested={"est_revenue"})

    assert resolved[0].value == 5_000_000.0


def test_map_entity_never_returns_a_field_it_could_not_resolve() -> None:
    entity = DiffbotOrganization()  # every field unset

    resolved = _map_entity(entity, requested=_ALL_SELLER_FIELDS)

    assert resolved == []


def test_map_entity_ignores_an_invalid_founding_date() -> None:
    entity = DiffbotOrganization(foundingDate=DiffbotDate(str="not-a-date"))

    resolved = _map_entity(entity, requested={"foundation_date", "years_active"})

    assert resolved == []


def test_parse_founding_date_strips_diffbots_precision_prefix() -> None:
    """Diffbot's real Enhance API returns `foundingDate.str` as e.g.
    `"d2010-01-01"` — a precision character prefix, not a bare ISO date —
    confirmed against a live account (Stripe lookup).
    """
    assert _parse_founding_date("d2010-01-01") == date(2010, 1, 1)


def test_parse_founding_date_rejects_unparseable_input() -> None:
    assert _parse_founding_date("not-a-date") is None
    assert _parse_founding_date("") is None


def test_request_timeout_is_bounded() -> None:
    """A background enrichment run must not hang on aiohttp's 300s default
    when Diffbot is slow or unreachable.
    """
    assert _REQUEST_TIMEOUT.total is not None
    assert 0 < _REQUEST_TIMEOUT.total <= 30
