import pytest

from app.modules.discovery.domain.drafts import draft_from_lead, hostname, websites_match
from app.modules.discovery.domain.leads import DiscoveredLead


def test_draft_from_lead_maps_category_to_a_sector_focus_guess() -> None:
    lead = DiscoveredLead(
        name="Acme Co", source_url="https://example.com", category="Retail / E-Commerce"
    )

    draft = draft_from_lead(lead)

    assert draft.org_name == "Acme Co"
    assert draft.values == {"sector_focus": ["Retail / E-Commerce"]}
    assert draft.source_urls == ("https://example.com",)


def test_draft_from_lead_never_maps_address_to_hq_country() -> None:
    """A street address is not a country — there is no organization field
    it maps onto, so it must never be silently prefilled into one.
    """
    lead = DiscoveredLead(
        name="Acme Co", source_url="https://example.com", address="123 Main St, Austin, TX"
    )

    draft = draft_from_lead(lead)

    assert "hq_country" not in draft.values
    assert draft.values == {}


def test_draft_from_lead_maps_country_to_hq_country_as_a_bare_string() -> None:
    """`hq_country` is `multi_select_as_text` — a bare string, unlike
    `sector_focus`'s `multi_select_text`, which takes a list.
    """
    lead = DiscoveredLead(
        name="Acme Co", source_url="https://example.com", country="United Arab Emirates"
    )

    draft = draft_from_lead(lead)

    assert draft.values == {"hq_country": "United Arab Emirates"}


def test_draft_from_lead_omits_hq_country_when_lead_has_none() -> None:
    lead = DiscoveredLead(name="Acme Co", source_url="https://example.com")

    draft = draft_from_lead(lead)

    assert "hq_country" not in draft.values


def test_draft_from_lead_maps_website_to_domains_as_a_bare_hostname() -> None:
    """`domains` is `text_list` — a list, like `sector_focus`, not a bare
    string like `hq_country` — and Attio's `domains` attribute is
    domain-typed, so the scheme and path from Places' `websiteUri` must be
    stripped down to the host.
    """
    lead = DiscoveredLead(
        name="Acme Co",
        source_url="https://example.com",
        website="https://www.acme.example.com/contact?ref=maps",
    )

    draft = draft_from_lead(lead)

    assert draft.values == {"domains": ["acme.example.com"]}


def test_draft_from_lead_omits_domains_when_lead_has_no_website() -> None:
    lead = DiscoveredLead(name="Acme Co", source_url="https://example.com")

    draft = draft_from_lead(lead)

    assert "domains" not in draft.values


def test_draft_from_lead_omits_domains_when_the_website_has_no_host() -> None:
    """A malformed `websiteUri` (rare, but Places gives no format
    guarantee) must not silently prefill a garbage `domains` entry.
    """
    lead = DiscoveredLead(name="Acme Co", source_url="https://example.com", website="not-a-url")

    draft = draft_from_lead(lead)

    assert "domains" not in draft.values


def test_draft_from_lead_does_not_raise_on_a_website_urlsplit_cannot_parse() -> None:
    """`urlsplit` raises `ValueError` on a handful of malformed hosts (an
    unbalanced IPv6 bracket) rather than just returning no hostname —
    `draft_from_lead` must degrade the same way as any other bad-input
    case, not propagate an exception out of a pure mapping function.
    """
    lead = DiscoveredLead(name="Acme Co", source_url="https://example.com", website="http://[::1")

    draft = draft_from_lead(lead)

    assert "domains" not in draft.values


def test_hostname_accepts_schemeless_provider_websites() -> None:
    assert hostname("acme.com") == "acme.com"
    assert hostname("www.Acme.com/about") == "acme.com"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("https://www.acme.com/contact", "acme.com", True),
        ("https://shop.acme.com", "http://acme.com", True),
        ("https://acme.com", "acme.de", False),
        ("https://acme.com", "notacme.com", False),
        ("https://acme.com", "", False),
        ("http://[::1", "acme.com", False),
    ],
)
def test_websites_match(a: str, b: str, expected: bool) -> None:
    assert websites_match(a, b) is expected
