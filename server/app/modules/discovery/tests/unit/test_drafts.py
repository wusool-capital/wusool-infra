from app.modules.discovery.domain.drafts import draft_from_lead
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
