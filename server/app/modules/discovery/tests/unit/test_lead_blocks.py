"""`build_needs_review_blocks` — the website-check card for a lead whose
enrichment provider disagreed with Maps about its website.
"""

from app.modules.discovery.api.dependencies import decode_draft
from app.modules.discovery.api.slack.views import build_needs_review_blocks
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.outcome import ReviewValue, UnverifiedSeller


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
