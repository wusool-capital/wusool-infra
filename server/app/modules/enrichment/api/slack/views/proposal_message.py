"""Renders a proposal as a Slack *message*, not a modal — `propose()` (a
web search + an LLM call) routinely runs past Slack's 3-second `trigger_id`
budget, so it must run in the background after `ack()` the same way
`/find-match` does (see `matching_engine.api.dependencies.run_match_and_post`),
and a `views_open` modal needs a fresh `trigger_id` a background task no
longer has. The message shows every proposed field for review, with one
"Review & Save" button — clicking it (a fresh `trigger_id`, from that
click) opens `ddl_commands`' real edit form, prefilled, so the operator
reviews/edits everything in one place and submits once, through the
ordinary edit-form write path.
"""

import json
import uuid
from datetime import date

from slack_sdk.models.blocks import Block, ContextBlock, DividerBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.enrichment.domain.field_plans import WriteTarget, enrichable_fields_by_name_for
from app.modules.enrichment.domain.proposals import (
    EnrichmentProposal,
    FieldValue,
    ProposedFieldValue,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.notifications import sanitize_mrkdwn


def _json_safe(value: FieldValue) -> FieldValue:
    """`ProposedFieldValue.proposed` can be a native `date` (coerced in
    `EnrichMixin`) — `json.dumps` can't serialize that, so it goes into the
    button value as an ISO string; `decode_proposal` converts it back for
    the one kind (`date`) that needs a real object.
    """
    return value.isoformat() if isinstance(value, date) else value


def _encode_proposal(proposal: EnrichmentProposal) -> str:
    """Only what `EnrichmentReviewPort.open_review_form` actually needs to
    build the edit form — `current`/`source_url`/`confidence`/`rationale`
    are display-only and dropped here to keep the button value well under
    Slack's 2000-char limit regardless of how many fields were proposed.
    """
    return json.dumps(
        {
            "kind": proposal.target.kind.value,
            "role_id": str(proposal.target.role_id),
            "org_attio_id": proposal.target.org_attio_id,
            "org_name": proposal.target.org_name,
            "values": [
                {
                    "field_name": v.field_name,
                    "write_target": v.write_target.value,
                    "proposed": _json_safe(v.proposed),
                }
                for v in proposal.values
            ],
        }
    )


def decode_proposal(value: str) -> EnrichmentProposal:
    data = json.loads(value)
    kind = data["kind"]
    fields_by_name = enrichable_fields_by_name_for(kind)
    target = EnrichmentTarget(
        kind=EnrichmentTargetKind(kind),
        role_id=uuid.UUID(data["role_id"]),
        org_attio_id=data["org_attio_id"],
        org_name=data["org_name"],
    )
    values = []
    for v in data["values"]:
        field = fields_by_name.get(v["field_name"])
        proposed = v["proposed"]
        if field is not None and field.kind == "date" and isinstance(proposed, str):
            proposed = date.fromisoformat(proposed)
        values.append(
            ProposedFieldValue(
                field_name=v["field_name"],
                write_target=WriteTarget(v["write_target"]),
                current=None,
                proposed=proposed,
                source_url="",
                confidence=0.0,
                rationale="",
            )
        )
    return EnrichmentProposal(target=target, values=tuple(values), generated_by_model="")


def _render_proposed_value(value: FieldValue) -> str:
    """A URL-shaped proposed value (logo_url, linkedin, twitter, etc.) is
    unreadable as raw text in Slack — Diffbot's own logo_url in particular
    is an encoded image-proxy link, not a plain URL. Render any http(s) URL
    as a short clickable link instead of dumping the raw string.
    """
    text = str(value)
    if text.startswith("http://") or text.startswith("https://"):
        return f"<{text}|View>"
    return sanitize_mrkdwn(text)


def build_proposal_blocks(proposal: EnrichmentProposal) -> list[Block]:
    if not proposal.values:
        return [
            SectionBlock(
                text=f"*{sanitize_mrkdwn(proposal.target.org_name)}*\n"
                "No new field values found from public sources."
            )
        ]

    blocks: list[Block] = [
        SectionBlock(text=f"*Proposed enrichment for {sanitize_mrkdwn(proposal.target.org_name)}*"),
        DividerBlock(),
    ]
    for value in proposal.values:
        current = value.current if value.current not in (None, "") else "_(empty)_"
        blocks.append(
            SectionBlock(
                text=(
                    f"*{value.field_name}*\n"
                    f"Current: {sanitize_mrkdwn(str(current))}\n"
                    f"Proposed: *{_render_proposed_value(value.proposed)}*\n"
                    f"Confidence: {value.confidence:.0%} — {sanitize_mrkdwn(value.rationale)}"
                )
            )
        )
        blocks.append(
            ContextBlock(elements=[MarkdownTextObject(text=f"<{value.source_url}|source>")])
        )

    blocks.append(DividerBlock())
    blocks.append(
        SectionBlock(
            text="Review these values in the edit form before they're saved.",
            accessory=ButtonElement(
                action_id="enrichment_review",
                text="Review & Save",
                style="primary",
                value=_encode_proposal(proposal),
            ),
        )
    )
    return blocks
