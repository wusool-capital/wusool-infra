"""Coverage for `encode_lead`/`decode_lead` — round-trips a `DiscoveredLead`
through a Slack button `value`. Built off `dataclasses.asdict`/`**kwargs`
rather than a hand-written field list, specifically so a field added to
`DiscoveredLead` can't silently go unencoded or undecoded.
"""

from app.modules.discovery.api.dependencies import decode_lead, encode_lead
from app.modules.discovery.domain.leads import DiscoveredLead


def test_round_trips_every_field() -> None:
    lead = DiscoveredLead(
        name="Acme Rollup",
        source_url="https://example.com/acme",
        address="123 Main St",
        category="logistics",
    )

    assert decode_lead(encode_lead(lead)) == lead


def test_round_trips_optional_fields_left_unset() -> None:
    lead = DiscoveredLead(name="Acme Rollup", source_url="https://example.com/acme")

    assert decode_lead(encode_lead(lead)) == lead
