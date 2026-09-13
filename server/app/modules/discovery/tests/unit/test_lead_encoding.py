"""Coverage for `encode_lead`/`decode_lead` — round-trips a `DiscoveredLead`
through a Slack button `value` via `utilities`' shared ephemeral store
(`encode_lead` returns a token, not the JSON itself). Built off
`dataclasses.asdict`/`**kwargs` rather than a hand-written field list,
specifically so a field added to `DiscoveredLead` can't silently go
unencoded or undecoded.
"""

import pytest

from app.modules.discovery.api.dependencies import decode_lead, encode_lead
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.utilities import NotFoundError


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


def test_encode_lead_returns_a_short_token_even_for_an_unusually_long_lead() -> None:
    """`DiscoveredLead`'s field count is fixed, but a single field (an
    unusual Maps `name`/`address`) could still be long enough to blow past
    Slack's 2000-char button-value cap on its own — the token must stay
    short regardless.
    """
    lead = DiscoveredLead(
        name="A " * 1500,
        source_url="https://example.com/acme",
        address="B " * 1500,
    )

    token = encode_lead(lead)

    assert len(token) <= 2000
    assert decode_lead(token) == lead


def test_decode_lead_raises_not_found_for_an_unknown_token() -> None:
    with pytest.raises(NotFoundError):
        decode_lead("not-a-real-token")
