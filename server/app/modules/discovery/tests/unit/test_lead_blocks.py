"""`build_possible_duplicate_blocks` — each lead gets two actions (View on
Maps, Add as seller), which Slack requires as an `ActionsBlock` since a
`SectionBlock` allows only one accessory button.
"""

from app.modules.discovery.api.dependencies import decode_lead
from app.modules.discovery.api.slack.views import build_possible_duplicate_blocks
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.domain.outcome import PossibleDuplicate


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
    # `encode_lead` returns a fresh store token each call — compare by decoding.
    assert decode_lead(add_as_seller["value"]) == lead


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
