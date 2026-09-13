"""`candidate_names`/`prefill` grow with search-result count and with
however many fields a prefill source populated — same shape that overran
`enrichment`'s button `value` (see `proposal_message.py`'s tests). Both are
stored server-side and only a token rides in `private_metadata`.
"""

import json

from app.models import Organization
from app.modules.ddl_commands.api.slack.views.organization_selection import (
    build_organization_selection_modal,
    decode_selection_payload,
)
from app.modules.utilities import get_shared_ephemeral_store


def test_private_metadata_stays_small_regardless_of_candidate_and_prefill_size() -> None:
    """Regression for the same class of bug as `/enrich-buyer Stripe`: a
    large candidate list and prefill dict must not grow `private_metadata`
    past Slack's 3000-char cap.
    """
    candidates = [Organization(attio_id=f"org-{i}", name="A " * 200) for i in range(25)]
    prefill = {f"field_{i}": "A " * 200 for i in range(20)}

    view = build_organization_selection_modal(
        candidates,
        kind="seller",
        search_term="Acme",
        requested_by="U_TEST",
        channel_id="C_TEST",
        prefill=prefill,
    )

    assert len(view.private_metadata) <= 3000


def test_private_metadata_round_trips_candidate_names_and_prefill() -> None:
    candidates = [Organization(attio_id="org-1", name="Acme Corp")]

    view = build_organization_selection_modal(
        candidates,
        kind="seller",
        search_term="Acme",
        requested_by="U_TEST",
        channel_id="C_TEST",
        prefill={"est_revenue": 5_000_000.0},
    )

    metadata = json.loads(view.private_metadata)
    candidate_names, prefill = decode_selection_payload(metadata["payload_token"])

    assert candidate_names == ["Acme Corp"]
    assert prefill == {"est_revenue": 5_000_000.0}


def test_decode_selection_payload_degrades_to_empty_for_an_unknown_token() -> None:
    """Losing the duplicate-candidates list or a discovery prefill on an
    expired token is a worse-prefilled form, not a broken submission — so
    this degrades rather than raising (contrast `enrichment.decode_proposal`,
    which raises, because there its payload *is* the whole point of the
    submission).
    """
    assert decode_selection_payload("not-a-real-token") == ([], {})


def test_decode_selection_payload_degrades_to_empty_for_a_missing_token() -> None:
    """A modal submitted mid-deploy — built by the previous version's
    schema, which has no `payload_token` key at all — passes `None` here,
    not a string; this must degrade the same way an expired token does,
    not raise.
    """
    assert decode_selection_payload(None) == ([], {})


def test_encoded_payload_is_stored_in_the_shared_ephemeral_store() -> None:
    candidates = [Organization(attio_id="org-1", name="Acme Corp")]

    view = build_organization_selection_modal(
        candidates,
        kind="seller",
        search_term="Acme",
        requested_by="U_TEST",
        channel_id="C_TEST",
    )

    metadata = json.loads(view.private_metadata)
    assert get_shared_ephemeral_store().get(metadata["payload_token"]) is not None
