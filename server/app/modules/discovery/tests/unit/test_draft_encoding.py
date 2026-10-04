"""Coverage for `encode_draft`/`decode_draft` — round-trips a `SellerDraft`
through a Slack button `value` via `utilities`' shared ephemeral store
(`encode_draft` returns a token, not the JSON itself).
"""

from datetime import date

import pytest

from app.modules.discovery.api.dependencies import decode_draft, encode_draft
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.utilities import NotFoundError


def test_round_trips_every_field() -> None:
    draft = SellerDraft(
        org_name="Acme Rollup",
        values={"hq_country": "United Arab Emirates", "domains": ["acme.example"]},
        source_urls=("https://maps.example/acme",),
        source_place_id="p1",
    )

    decoded = decode_draft(encode_draft(draft))

    assert decoded == draft
    assert isinstance(decoded.source_urls, tuple)


def test_a_date_value_comes_back_as_an_iso_string() -> None:
    """`ddl_commands`' `wrap_prefill_value` turns it back into a date."""
    draft = SellerDraft(org_name="Acme", values={"foundation_date": date(2015, 3, 1)})

    assert decode_draft(encode_draft(draft)).values == {"foundation_date": "2015-03-01"}


def test_encode_draft_returns_a_short_token_even_for_a_long_draft() -> None:
    draft = SellerDraft(org_name="A " * 1500, values={"description": "B " * 1500})

    token = encode_draft(draft)

    assert len(token) <= 2000
    assert decode_draft(token) == draft


def test_decode_draft_raises_not_found_for_an_unknown_token() -> None:
    with pytest.raises(NotFoundError):
        decode_draft("not-a-real-token")
