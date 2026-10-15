"""Coverage for `decode_draft` — resolves the token an older Slack button
carries back to a `SellerDraft` via `utilities`' shared ephemeral store.
"""

from datetime import date

import pytest

from app.modules.discovery.api.dependencies import decode_draft
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.tests.fakes.drafts import store_draft
from app.modules.utilities import NotFoundError


def test_round_trips_every_field() -> None:
    draft = SellerDraft(
        org_name="Acme Rollup",
        values={"hq_country": "United Arab Emirates", "domains": ["acme.example"]},
        source_urls=("https://maps.example/acme",),
        source_place_id="p1",
    )

    decoded = decode_draft(store_draft(draft))

    assert decoded == draft
    assert isinstance(decoded.source_urls, tuple)


def test_a_date_value_comes_back_as_an_iso_string() -> None:
    """`ddl_commands`' `wrap_prefill_value` turns it back into a date."""
    draft = SellerDraft(org_name="Acme", values={"foundation_date": date(2015, 3, 1)})

    assert decode_draft(store_draft(draft)).values == {"foundation_date": "2015-03-01"}


def test_a_long_draft_still_resolves_from_a_short_token() -> None:
    draft = SellerDraft(org_name="A " * 1500, values={"description": "B " * 1500})

    token = store_draft(draft)

    assert len(token) <= 2000
    assert decode_draft(token) == draft


def test_decode_draft_raises_not_found_for_an_unknown_token() -> None:
    with pytest.raises(NotFoundError):
        decode_draft("not-a-real-token")
