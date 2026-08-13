"""Slack result message (§20) — concise: score, data confidence, a brief
rationale per candidate, plus "View Full Analysis"/"Approve"/"Reject"
actions. Block Kit builders only, no logic.
"""

from app.modules.matching.application.use_cases import MatchRunResult


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
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Only {len(result.results)} qualifying candidate"
                            f"{'s' if len(result.results) != 1 else ''} available "
                            "— fewer than 3."
                        ),
                    }
                ],
            }
        )

    for candidate in result.results:
        rationale = candidate.why_it_matches or "No rationale available."
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{candidate.rank}. {candidate.seller_org_name} — "
                        f"{candidate.match_score:.0f}/100*\n"
                        f"Data confidence: {candidate.data_confidence:.0f}/100\n"
                        f"{rationale}"
                    ),
                },
            }
        )
        blocks.append(
            {
                "type": "actions",
                "block_id": f"match_actions_{candidate.match_result_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Full Analysis"},
                        "action_id": "view_full_analysis",
                        "value": result.run_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve Match"},
                        "action_id": "approve_match",
                        "style": "primary",
                        "value": candidate.match_result_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject Match"},
                        "action_id": "reject_match",
                        "style": "danger",
                        "value": candidate.match_result_id,
                    },
                ],
            }
        )

    return blocks
