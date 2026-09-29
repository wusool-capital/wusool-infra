"""Sellers `discovery` auto-created for a run, as a message of their own so
CRM-shortlist and discovered rows can each be refreshed in place after an
Approve/Reject without overwriting the other. Unscored, so no score line and
no "View Full Analysis"; the buttons reuse `approve_match`/`reject_match`.
Block Kit builders only, no logic.
"""

from collections.abc import Sequence

from slack_sdk.models.blocks import ActionsBlock, Block, ContextBlock, DividerBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.matching_engine.application.matching.use_cases import MatchResultView
from app.modules.notifications import sanitize_mrkdwn


def build_discovered_candidates_blocks(
    results: Sequence[MatchResultView], *, notes: Sequence[str] = ()
) -> list[Block]:
    blocks: list[Block] = [
        ContextBlock(
            elements=[
                MarkdownTextObject(
                    text=(
                        f"*{len(results)} new seller(s)* found via Google Maps and added to the "
                        "CRM. Unverified and unscored; approve to open a Qualified deal."
                    )
                )
            ]
        ),
        DividerBlock(),
    ]
    for candidate in results:
        blocks.extend(_candidate_blocks(candidate))
    blocks.extend(
        ContextBlock(elements=[MarkdownTextObject(text=f"_{sanitize_mrkdwn(note)}_")])
        for note in notes
    )
    return blocks


def _candidate_blocks(candidate: MatchResultView) -> list[Block]:
    text = f"*{candidate.rank}. {sanitize_mrkdwn(candidate.seller_org_name)}*"
    if candidate.source_url:
        text += f"\n<{candidate.source_url}|View on Maps>"
    blocks: list[Block] = [SectionBlock(text=text)]

    if candidate.status == "PENDING_REVIEW":
        blocks.append(
            ActionsBlock(
                block_id=f"match_actions_{candidate.match_result_id}",
                elements=[
                    ButtonElement(
                        text="Approve Match",
                        action_id="approve_match",
                        style="primary",
                        value=candidate.match_result_id,
                    ),
                    ButtonElement(
                        text="Reject Match",
                        action_id="reject_match",
                        style="danger",
                        value=candidate.match_result_id,
                    ),
                ],
            )
        )
    else:
        emoji = {"APPROVED": "✅", "REJECTED": "❌"}.get(candidate.decision or "", "•")
        who = f" by <@{candidate.approved_by}>" if candidate.approved_by else ""
        blocks.append(
            ContextBlock(elements=[MarkdownTextObject(text=f"{emoji} *{candidate.status}*{who}")])
        )
    return blocks
