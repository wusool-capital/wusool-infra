"""Slack result message (§20) — concise: score, data confidence, a brief
rationale per candidate, plus "Enrich"/"View Full Analysis"/"Approve"/
"Reject" actions. Block Kit builders only, no logic.

Also builds the same message's *refreshed* state after an Approve/Reject
action (`build_match_result_blocks_from_view`) — a decided candidate shows
a static "Approved/Rejected by ..." line instead of buttons, so the
original message doesn't keep looking actionable once it's been acted on.
"""

from slack_sdk.models.blocks import ActionsBlock, Block, ContextBlock, DividerBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.matching_engine.application.matching.use_cases import (
    MatchRunResult,
    MatchRunView,
)
from app.modules.notifications import sanitize_mrkdwn


def build_match_result_blocks(result: MatchRunResult) -> list[Block]:
    if result.status == "FAILED":
        return [
            SectionBlock(
                text=(
                    f"*Matching failed for {result.buyer_org_name}*\n"
                    "Matching failed before results could be generated. "
                    f"{result.error or ''}"
                )
            )
        ]

    if not result.results:
        return [
            SectionBlock(
                text=(
                    f"*{result.buyer_org_name}*\n"
                    "No qualifying seller candidates were available for this buyer."
                )
            ),
            _discover_more_sellers_actions(result.run_id),
        ]

    blocks: list[Block] = [
        SectionBlock(text=f"*Buyer:*\n{result.buyer_org_name}"),
        DividerBlock(),
    ]

    if len(result.results) < 3:
        blocks.append(_fewer_than_three_context(len(result.results)))

    for candidate in result.results:
        blocks.extend(
            _candidate_block(
                run_id=result.run_id,
                match_result_id=candidate.match_result_id,
                seller_role_id=candidate.seller_role_id,
                rank=candidate.rank,
                seller_org_name=candidate.seller_org_name,
                match_score=candidate.match_score,
                data_confidence=candidate.data_confidence,
                why_it_matches=candidate.why_it_matches,
                status="PENDING_REVIEW",
                approved_by=None,
                decision=None,
            )
        )

    blocks.append(_discover_more_sellers_actions(result.run_id))
    return blocks


def build_match_result_blocks_from_view(view: MatchRunView) -> list[Block]:
    """Same message, rebuilt from persisted state — used to update the
    original message in place after an Approve/Reject action.
    """
    blocks: list[Block] = [
        SectionBlock(text=f"*Buyer:*\n{view.buyer_org_name}"),
        DividerBlock(),
    ]

    if len(view.results) < 3:
        blocks.append(_fewer_than_three_context(len(view.results)))

    for candidate in view.results:
        blocks.extend(
            _candidate_block(
                run_id=view.run_id,
                match_result_id=candidate.match_result_id,
                seller_role_id=candidate.seller_role_id,
                rank=candidate.rank,
                seller_org_name=candidate.seller_org_name,
                match_score=candidate.match_score,
                data_confidence=candidate.data_confidence,
                why_it_matches=candidate.why_it_matches,
                status=candidate.status,
                approved_by=candidate.approved_by,
                decision=candidate.decision,
            )
        )

    blocks.append(_discover_more_sellers_actions(view.run_id))
    return blocks


def _discover_more_sellers_actions(run_id: str) -> ActionsBlock:
    """Operator-triggered counterpart to the automatic below-threshold
    discovery call in `api.dependencies.trigger_seller_discovery` — same
    search, available on demand rather than only when the CRM shortlist is
    weak. Handled by `handlers/actions.py::handle_discover_more_sellers`.
    """
    return ActionsBlock(
        block_id=f"discover_actions_{run_id}",
        elements=[
            ButtonElement(text="Find more sellers", action_id="discover_more_sellers", value=run_id)
        ],
    )


def _fewer_than_three_context(count: int) -> ContextBlock:
    return ContextBlock(
        elements=[
            MarkdownTextObject(
                text=(
                    f"Only {count} qualifying candidate{'s' if count != 1 else ''} available "
                    "— fewer than 3."
                )
            )
        ]
    )


def _candidate_block(
    *,
    run_id: str,
    match_result_id: str,
    seller_role_id: str | None,
    rank: int,
    seller_org_name: str,
    match_score: float,
    data_confidence: float,
    why_it_matches: str | None,
    status: str,
    approved_by: str | None,
    decision: str | None,
) -> list[Block]:
    rationale = sanitize_mrkdwn(why_it_matches) if why_it_matches else "No rationale available."
    blocks: list[Block] = [
        SectionBlock(
            text=(
                f"*{rank}. {seller_org_name} — {match_score:.0f}/100*\n"
                f"Data confidence: {data_confidence:.0f}/100\n"
                f"{rationale}"
            )
        )
    ]

    if status == "PENDING_REVIEW":
        elements = [
            ButtonElement(text="View Full Analysis", action_id="view_full_analysis", value=run_id),
            ButtonElement(
                text="Approve Match",
                action_id="approve_match",
                style="primary",
                value=match_result_id,
            ),
            ButtonElement(
                text="Reject Match",
                action_id="reject_match",
                style="danger",
                value=match_result_id,
            ),
        ]
        blocks.append(ActionsBlock(block_id=f"match_actions_{match_result_id}", elements=elements))
        if seller_role_id:
            blocks.append(
                ContextBlock(
                    elements=[
                        MarkdownTextObject(
                            text=f"Run `/enrich-seller {sanitize_mrkdwn(seller_org_name)}` "
                            "to research missing fields."
                        )
                    ]
                )
            )
    else:
        emoji = {"APPROVED": "✅", "REJECTED": "❌"}.get(decision or "", "•")
        who = f" by <@{approved_by}>" if approved_by else ""
        blocks.append(ContextBlock(elements=[MarkdownTextObject(text=f"{emoji} *{status}*{who}")]))

    return blocks
