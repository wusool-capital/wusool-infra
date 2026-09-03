"""Slack result message (§20) — concise: score, data confidence, a brief
rationale per candidate, plus "View Full Analysis"/"Approve"/"Reject"
actions. Block Kit builders only, no logic.

Also builds the same message's *refreshed* state after an Approve/Reject
action (`build_match_result_blocks_from_view`) — a decided candidate shows
a static "Approved/Rejected by ..." line instead of buttons, so the
original message doesn't keep looking actionable once it's been acted on.
"""

from app.modules.matching_engine.application.matching.use_cases import (
    MatchRunResult,
    MatchRunView,
)
from app.modules.notifications import sanitize_mrkdwn


def build_match_result_blocks(result: MatchRunResult) -> list[dict]:
    if result.status == "FAILED":
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Matching failed for {result.buyer_org_name}*\n"
                        "Matching failed before results could be generated. "
                        f"{result.error or ''}"
                    ),
                },
            }
        ]

    if not result.results:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{result.buyer_org_name}*\n"
                        "No qualifying seller candidates were available for this buyer."
                    ),
                },
            }
        ]

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Buyer:*\n{result.buyer_org_name}"},
        },
        {"type": "divider"},
    ]

    if len(result.results) < 3:
        blocks.append(_fewer_than_three_context(len(result.results)))

    for candidate in result.results:
        blocks.extend(
            _candidate_block(
                run_id=result.run_id,
                match_result_id=candidate.match_result_id,
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

    return blocks


def build_match_result_blocks_from_view(view: MatchRunView) -> list[dict]:
    """Same message, rebuilt from persisted state — used to update the
    original message in place after an Approve/Reject action.
    """
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Buyer:*\n{view.buyer_org_name}"},
        },
        {"type": "divider"},
    ]

    if len(view.results) < 3:
        blocks.append(_fewer_than_three_context(len(view.results)))

    for candidate in view.results:
        blocks.extend(
            _candidate_block(
                run_id=view.run_id,
                match_result_id=candidate.match_result_id,
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

    return blocks


def _fewer_than_three_context(count: int) -> dict:
    return {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": (
                    f"Only {count} qualifying candidate{'s' if count != 1 else ''} available "
                    "— fewer than 3."
                ),
            }
        ],
    }


def _candidate_block(
    *,
    run_id: str,
    match_result_id: str,
    rank: int,
    seller_org_name: str,
    match_score: float,
    data_confidence: float,
    why_it_matches: str | None,
    status: str,
    approved_by: str | None,
    decision: str | None,
) -> list[dict]:
    rationale = sanitize_mrkdwn(why_it_matches) if why_it_matches else "No rationale available."
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{rank}. {seller_org_name} — {match_score:.0f}/100*\n"
                    f"Data confidence: {data_confidence:.0f}/100\n"
                    f"{rationale}"
                ),
            },
        }
    ]

    if status == "PENDING_REVIEW":
        blocks.append(
            {
                "type": "actions",
                "block_id": f"match_actions_{match_result_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Full Analysis"},
                        "action_id": "view_full_analysis",
                        "value": run_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve Match"},
                        "action_id": "approve_match",
                        "style": "primary",
                        "value": match_result_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject Match"},
                        "action_id": "reject_match",
                        "style": "danger",
                        "value": match_result_id,
                    },
                ],
            }
        )
    else:
        emoji = {"APPROVED": "✅", "REJECTED": "❌"}.get(decision or "", "•")
        who = f" by <@{approved_by}>" if approved_by else ""
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"{emoji} *{status}*{who}"}],
            }
        )

    return blocks
