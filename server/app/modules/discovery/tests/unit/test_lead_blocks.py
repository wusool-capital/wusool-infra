"""`build_possible_duplicate_blocks` — each lead gets two actions (View on
Maps, Add as seller), which Slack requires as an `ActionsBlock` since a
`SectionBlock` allows only one accessory button.
"""

from app.modules.discovery.api.dependencies import decode_draft
from app.modules.discovery.api.slack.views import (
    build_needs_review_blocks,
    build_possible_duplicate_blocks,
)
from app.modules.discovery.domain.drafts import SellerDraft, draft_from_lead
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.domain.outcome import PossibleDuplicate, ReviewValue, UnverifiedSeller


def _dup(lead: DiscoveredLead, existing: str = "Acme Holdings") -> PossibleDuplicate:
    return PossibleDuplicate(lead=lead, existing_org_name=existing)


def test_no_duplicates_renders_nothing() -> None:
    assert build_possible_duplicate_blocks([]) == []


def test_each_lead_gets_a_view_on_maps_and_add_as_seller_button() -> None:
    lead = DiscoveredLead(
        name="Acme Co",
        source_url="https://www.google.com/maps/place/Acme+Co/data=!4m7",
        address="123 Main St",
    )

    blocks = build_possible_duplicate_blocks([_dup(lead)])
    actions = blocks[3].to_dict()
    elements = actions["elements"]

    assert actions["type"] == "actions"
    assert len(elements) == 2

    view_on_maps, add_as_seller = elements
    assert view_on_maps["action_id"] == "view_web_lead_source"
    assert view_on_maps["url"] == lead.source_url
    assert add_as_seller["action_id"] == "discover_add_seller"
    assert add_as_seller["text"]["text"] == "Add as seller"
    # `encode_draft` returns a fresh store token each call — compare by decoding.
    assert decode_draft(add_as_seller["value"]) == draft_from_lead(lead)


def test_the_existing_org_it_may_duplicate_is_named() -> None:
    lead = DiscoveredLead(name="Acme Co", source_url="https://maps.example.com/acme")

    blocks = build_possible_duplicate_blocks([_dup(lead, existing="Acme Holdings")])

    assert "Possibly the same as *Acme Holdings*" in blocks[2].to_dict()["text"]["text"]


def test_a_lead_with_a_website_shows_it() -> None:
    lead = DiscoveredLead(
        name="Acme Co",
        source_url="https://maps.example.com/acme",
        website="https://acme.example.com",
    )

    blocks = build_possible_duplicate_blocks([_dup(lead)])

    assert "https://acme.example.com" in blocks[2].to_dict()["text"]["text"]


def test_multiple_leads_each_get_their_own_actions_block() -> None:
    leads = [
        DiscoveredLead(name="Acme Co", source_url="https://maps.example.com/acme"),
        DiscoveredLead(name="Beta Co", source_url="https://maps.example.com/beta"),
    ]

    blocks = build_possible_duplicate_blocks([_dup(lead) for lead in leads])
    action_blocks = [b for b in blocks if b.to_dict().get("type") == "actions"]

    assert len(action_blocks) == 2
    assert action_blocks[0].to_dict()["elements"][0]["url"] == "https://maps.example.com/acme"
    assert action_blocks[1].to_dict()["elements"][0]["url"] == "https://maps.example.com/beta"


def test_needs_review_shows_both_websites_the_values_and_a_review_button() -> None:
    draft = SellerDraft(
        org_name="Acme Co",
        values={"domains": ["acme.com"], "employee_range": "11-50"},
        source_urls=("https://maps.example/acme",),
        source_place_id="p1",
    )
    unverified = UnverifiedSeller(
        draft=draft,
        maps_website="acme.com",
        provider_websites=(("Diffbot", "acme-group.de"), ("People Data Labs", None)),
        values=(ReviewValue("employee_range", "11-50", 0.9, "Sourced from Diffbot."),),
    )

    blocks = [b.to_dict() for b in build_needs_review_blocks(unverified)]

    assert blocks[0]["text"]["text"].startswith("*Website check for Acme Co*")
    assert blocks[2]["text"]["text"] == (
        "*website*\nGoogle Maps: acme.com\nDiffbot: acme-group.de\nPeople Data Labs: none"
    )
    assert blocks[3]["text"]["text"] == (
        "*employee_range*\nProposed: 11-50\nConfidence: 90% — Sourced from Diffbot."
    )
    button = blocks[-1]["accessory"]
    assert button["action_id"] == "discover_add_seller"
    assert button["text"]["text"] == "Review & Save"
    assert button["style"] == "primary"
    assert decode_draft(button["value"]) == draft


def test_needs_review_truncates_a_long_value_to_fit_slacks_section_limit() -> None:
    draft = SellerDraft(org_name="Acme Co", values={"description": "word " * 800})
    unverified = UnverifiedSeller(
        draft=draft,
        maps_website=None,
        provider_websites=(("Diffbot", "acme.com"),),
        values=(ReviewValue("description", "word " * 800, 0.9, "Sourced from Diffbot."),),
    )

    blocks = [b.to_dict() for b in build_needs_review_blocks(unverified)]

    assert all(len(b.get("text", {}).get("text", "")) <= 3000 for b in blocks)
    assert blocks[3]["text"]["text"].count("…") == 1
    assert decode_draft(blocks[-1]["accessory"]["value"]).values == draft.values


def test_a_stored_review_gets_a_durable_review_button() -> None:
    unverified = UnverifiedSeller(
        draft=SellerDraft(org_name="Acme Co", source_place_id="p1"),
        maps_website=None,
        provider_websites=(),
        values=(),
        review_id="p1",
    )

    button = build_needs_review_blocks(unverified)[-1].to_dict()["accessory"]

    assert (button["action_id"], button["value"]) == ("discover_review_seller", "p1")
