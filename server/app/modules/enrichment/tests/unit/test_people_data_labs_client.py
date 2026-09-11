"""Coverage for People Data Labs' field mapping — pure, no network."""

from datetime import date

from app.modules.enrichment.providers.people_data_labs.client import (
    _REQUEST_TIMEOUT,
    _map_response,
)
from app.modules.enrichment.providers.people_data_labs.schemas import (
    PdlCompanyResponse,
    PdlLocation,
)


def test_request_timeout_is_bounded() -> None:
    """A background enrichment run must not hang on aiohttp's 300s default
    when PDL is slow or unreachable.
    """
    assert _REQUEST_TIMEOUT.total is not None
    assert 0 < _REQUEST_TIMEOUT.total <= 30


def test_map_response_resolves_requested_fields_only() -> None:
    parsed = PdlCompanyResponse(
        summary="A logistics company.",
        founded=2015,
        estimated_num_employees=30,
        linkedin_url="https://linkedin.com/company/acme",
        location=PdlLocation(country="United Arab Emirates"),
        website="https://acme.com",
    )

    resolved = {
        f.field_name: f for f in _map_response(parsed, requested={"linkedin", "hq_country"})
    }

    assert set(resolved) == {"linkedin", "hq_country"}
    assert resolved["linkedin"].value == "https://linkedin.com/company/acme"
    assert resolved["hq_country"].value == "United Arab Emirates"
    assert resolved["linkedin"].provider == "People Data Labs"


def test_map_response_derives_foundation_date_and_years_active_from_founded_year() -> None:
    parsed = PdlCompanyResponse(founded=2015)

    resolved = {
        f.field_name: f
        for f in _map_response(parsed, requested={"foundation_date", "years_active"})
    }

    assert resolved["foundation_date"].value == date(2015, 1, 1)
    assert resolved["years_active"].value == date.today().year - 2015


def test_map_response_buckets_employee_count() -> None:
    parsed = PdlCompanyResponse(estimated_num_employees=30)

    resolved = {f.field_name: f for f in _map_response(parsed, requested={"employee_range"})}

    assert resolved["employee_range"].value == "11-50"


def test_map_response_never_proposes_revenue() -> None:
    """PDL's Company Enrichment API doesn't publish a revenue field at
    all — confirming there's no accidental mapping for it, since it's not
    in `PdlCompanyResponse` to begin with.
    """
    parsed = PdlCompanyResponse(founded=2015, estimated_num_employees=30)

    resolved = _map_response(parsed, requested={"est_revenue"})

    assert resolved == []


def test_map_response_with_nothing_set_resolves_nothing() -> None:
    parsed = PdlCompanyResponse()

    resolved = _map_response(parsed, requested={"linkedin", "hq_country", "description"})

    assert resolved == []
