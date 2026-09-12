"""Round-trip coverage for the "Review & Save" button's compact payload —
`_encode_proposal`/`decode_proposal` are the only place a proposal survives
a Slack round trip, and a `date`-kind field is the one value JSON can't
carry natively.
"""

import uuid
from datetime import date

from app.modules.enrichment.api.slack.views.proposal_message import (
    _encode_proposal,
    build_proposal_blocks,
    decode_proposal,
)
from app.modules.enrichment.domain.field_plans import WriteTarget
from app.modules.enrichment.domain.proposals import EnrichmentProposal, ProposedFieldValue
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind


def _proposal(values: tuple[ProposedFieldValue, ...]) -> EnrichmentProposal:
    target = EnrichmentTarget(
        kind=EnrichmentTargetKind.SELLER,
        role_id=uuid.uuid4(),
        org_attio_id="org-1",
        org_name="Acme Co",
    )
    return EnrichmentProposal(target=target, values=values, generated_by_model="test-model")


def test_round_trip_preserves_target_and_simple_values() -> None:
    proposal = _proposal(
        (
            ProposedFieldValue(
                field_name="est_revenue",
                write_target=WriteTarget.SELLER_ROLE,
                current=None,
                proposed=5_000_000.0,
                source_url="https://example.com",
                confidence=0.9,
                rationale="stated in press release",
            ),
        )
    )

    decoded = decode_proposal(_encode_proposal(proposal))

    assert decoded.target.kind == proposal.target.kind
    assert decoded.target.role_id == proposal.target.role_id
    assert decoded.target.org_attio_id == proposal.target.org_attio_id
    assert decoded.target.org_name == proposal.target.org_name
    assert len(decoded.values) == 1
    assert decoded.values[0].field_name == "est_revenue"
    assert decoded.values[0].proposed == 5_000_000.0
    assert decoded.values[0].write_target == WriteTarget.SELLER_ROLE


def test_round_trip_preserves_a_date_value_as_a_real_date() -> None:
    """`foundation_date` is a `date`-kind field — `json.dumps` can't
    serialize a raw `date`, so the button value carries an ISO string; the
    decoded proposal must still hand back a real `date`, not a string,
    since that's what `render_field_block`'s `date` branch requires.
    """
    proposal = _proposal(
        (
            ProposedFieldValue(
                field_name="foundation_date",
                write_target=WriteTarget.ORGANIZATION,
                current=None,
                proposed=date(2015, 3, 1),
                source_url="https://example.com",
                confidence=0.9,
                rationale="",
            ),
        )
    )

    encoded = _encode_proposal(proposal)
    assert "2015-03-01" in encoded  # confirms it went in JSON-safe, not raw

    decoded = decode_proposal(encoded)

    assert decoded.values[0].proposed == date(2015, 3, 1)
    assert isinstance(decoded.values[0].proposed, date)


def test_round_trip_drops_display_only_fields() -> None:
    """`current`/`source_url`/`confidence`/`rationale` are display-only —
    the button payload deliberately omits them to stay well under Slack's
    2000-char value limit regardless of how many fields were proposed.
    """
    proposal = _proposal(
        (
            ProposedFieldValue(
                field_name="est_revenue",
                write_target=WriteTarget.SELLER_ROLE,
                current=1_000_000.0,
                proposed=5_000_000.0,
                source_url="https://example.com",
                confidence=0.9,
                rationale="a long rationale that should not bloat the button payload",
            ),
        )
    )

    decoded = decode_proposal(_encode_proposal(proposal))

    assert decoded.values[0].current is None
    assert decoded.values[0].source_url == ""
    assert decoded.values[0].rationale == ""


def test_url_shaped_proposed_value_renders_as_a_short_link() -> None:
    """Diffbot's `logo_url` is an encoded image-proxy URL, unreadable as raw
    text — any http(s) proposed value should render as a short link, not the
    full string, so a reviewer isn't shown an unreadable wall of text.
    """
    proposal = _proposal(
        (
            ProposedFieldValue(
                field_name="logo_url",
                write_target=WriteTarget.ORGANIZATION,
                current=None,
                proposed="https://kg.diffbot.com/image/api/get?fetch=yes&url=abc123",
                source_url="https://example.com",
                confidence=0.9,
                rationale="Sourced from Diffbot.",
            ),
        )
    )

    blocks = build_proposal_blocks(proposal)
    field_block_text = blocks[2].text.text

    assert "<https://kg.diffbot.com/image/api/get?fetch=yes&url=abc123|View>" in field_block_text
    assert "kg.diffbot.com/image/api/get?fetch=yes&url=abc123*" not in field_block_text


def test_schemeless_domain_proposed_value_renders_as_a_link_not_literal_asterisks() -> None:
    """Diffbot's `linkedin`/`facebook` fields come back as bare domains
    (no `https://` prefix). Left unrendered, Slack still auto-linkifies the
    bare domain but the surrounding `*...*` bold markup shows up as literal
    asterisk characters instead of being interpreted as bold (confirmed
    live) — rendering it as an explicit link avoids that entirely.
    """
    proposal = _proposal(
        (
            ProposedFieldValue(
                field_name="linkedin",
                write_target=WriteTarget.ORGANIZATION,
                current=None,
                proposed="linkedin.com/company/camhatch",
                source_url="https://example.com",
                confidence=0.9,
                rationale="Sourced from Diffbot.",
            ),
        )
    )

    blocks = build_proposal_blocks(proposal)
    field_block_text = blocks[2].text.text

    assert "<https://linkedin.com/company/camhatch|View>" in field_block_text
    assert "*linkedin.com/company/camhatch*" not in field_block_text


def test_ordinary_text_with_a_period_is_not_mistaken_for_a_domain() -> None:
    """A description ending in an abbreviation like "Inc." must not be
    linkified — only a value that is *entirely* a domain-shaped string
    should be."""
    proposal = _proposal(
        (
            ProposedFieldValue(
                field_name="description",
                write_target=WriteTarget.ORGANIZATION,
                current=None,
                proposed="A logistics company, formerly Acme Inc.",
                source_url="https://example.com",
                confidence=0.9,
                rationale="Sourced from Diffbot.",
            ),
        )
    )

    blocks = build_proposal_blocks(proposal)
    field_block_text = blocks[2].text.text

    assert "Proposed: A logistics company, formerly Acme Inc." in field_block_text
    assert "<https://" not in field_block_text


def test_multiline_proposed_value_has_no_stray_asterisks() -> None:
    """Slack's `*bold*` markup doesn't reliably apply across a multi-line
    value — a long, multi-paragraph `description` used to be wrapped in
    `*...*` anyway and showed literal asterisk characters around it
    (confirmed live)."""
    long_description = (
        "CamHatch is the elegant solution to protect your online privacy. Why "
        "would you choose a post-it or sticker to cover your webcam if you can "
        "also choose an good-looking, unhackable and 100% secure solution?!\n"
        "CamHatch has been specifically developed to offer a minimalistic, "
        "easy-to-use solution for a 100% secure webcam."
    )
    proposal = _proposal(
        (
            ProposedFieldValue(
                field_name="description",
                write_target=WriteTarget.ORGANIZATION,
                current=None,
                proposed=long_description,
                source_url="https://example.com",
                confidence=0.9,
                rationale="Sourced from Diffbot.",
            ),
        )
    )

    blocks = build_proposal_blocks(proposal)
    field_block_text = blocks[2].text.text

    assert f"Proposed: {long_description}" in field_block_text
    assert "*CamHatch" not in field_block_text
    assert "webcam.*" not in field_block_text
