"""`filter_excluded_leads` — a buyer's `sector_exclusion` value has no way
to reach Google Maps' own search syntax (no dependable negation operator),
so this is the only place that exclusion can actually take effect.
"""

from app.modules.discovery.domain.leads import DiscoveredLead, filter_excluded_leads


def _lead(name: str, category: str | None = None) -> DiscoveredLead:
    return DiscoveredLead(name=name, source_url="https://example.com", category=category)


def test_returns_leads_unchanged_when_no_exclude_terms() -> None:
    leads = [_lead("Acme Clinics", "Healthcare"), _lead("Acme Construction", "Construction")]

    assert filter_excluded_leads(leads, ()) == leads


def test_drops_a_lead_whose_category_matches_an_exclude_term() -> None:
    leads = [_lead("Acme Clinics", "Healthcare"), _lead("Acme Construction", "Construction")]

    result = filter_excluded_leads(leads, ("construction",))

    assert result == [leads[0]]


def test_matching_is_case_insensitive() -> None:
    leads = [_lead("Acme Construction", "CONSTRUCTION")]

    assert filter_excluded_leads(leads, ("Construction",)) == []


def test_drops_a_lead_whose_name_matches_an_exclude_term_even_without_a_category() -> None:
    leads = [_lead("Acme Real Estate Group", category=None)]

    assert filter_excluded_leads(leads, ("real estate",)) == []


def test_multiple_exclude_terms_are_all_applied() -> None:
    leads = [
        _lead("Acme Clinics", "Healthcare"),
        _lead("Acme Construction", "Construction"),
        _lead("Acme Realty", "Real Estate"),
    ]

    result = filter_excluded_leads(leads, ("construction", "real estate"))

    assert result == [leads[0]]
