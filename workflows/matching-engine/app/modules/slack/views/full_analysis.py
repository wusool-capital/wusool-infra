""" "View Full Analysis" (§21) — rendered entirely from persisted data
(`MatchAnalysis`), never re-running Bedrock. Block Kit builders only.
"""

from app.modules.matching.schemas import MatchAnalysis, MatchResultRead, MatchScoreRead


def build_full_analysis_blocks(analysis: MatchAnalysis) -> list[dict]:
    blocks: list[dict] = []
    profile = analysis.run.requirement_profile

    blocks.append({"type": "header", "text": {"type": "plain_text", "text": "Buyer & Mandate"}})
    thesis = (profile or {}).get("strategic_thesis") or "Unknown"
    ideal_target = (profile or {}).get("ideal_target_description") or "Unknown"
    hard_reqs = (profile or {}).get("hard_requirements") or []
    hard_req_lines = (
        "\n".join(
            f"• {r.get('criterion')}: {r.get('value') or 'Unknown'} "
            f"({r.get('source')}, confirmed={r.get('human_confirmed')})"
            for r in hard_reqs
        )
        or "None extracted."
    )
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Strategic thesis:* {thesis}\n"
                    f"*Ideal target:* {ideal_target}\n"
                    f"*Hard requirements:*\n{hard_req_lines}"
                ),
            },
        }
    )
    blocks.append({"type": "divider"})

    blocks.append({"type": "header", "text": {"type": "plain_text", "text": "Top Matches"}})
    scores_by_id = {s.id: s for s in analysis.scores}
    for candidate in sorted(analysis.candidates, key=lambda c: c.rank or 0):
        blocks.extend(_candidate_blocks(candidate, scores_by_id))

    return blocks


def _candidate_blocks(candidate: MatchResultRead, scores_by_id: dict) -> list[dict]:
    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{candidate.rank}. Seller {candidate.seller_attio_id}* — "
                    f"{candidate.match_score}/100, confidence {candidate.data_confidence}/100\n"
                    f"Status: {candidate.status}"
                ),
            },
        }
    ]

    score: MatchScoreRead | None = None
    if candidate.match_score is not None:
        for s in scores_by_id.values():
            if s.seller_attio_id == candidate.seller_attio_id:
                score = s
                break

    criteria = ((score.dims or {}).get("criteria") if score else None) or []
    if criteria:
        criteria_lines = "\n".join(
            f"• {c.get('criterion')} ({c.get('criterion_type')}): {c.get('result')} "
            f"[{c.get('data_backing')}]"
            for c in criteria
        )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": criteria_lines}})

    narrative_bits = [
        ("Why it matches", score.reasoning if score else None),
        ("Why chosen over alternatives", candidate.why_chosen_over_alternatives),
        ("Recommended pitch", candidate.recommended_pitch),
        ("Risks and gaps", candidate.risks_and_gaps),
    ]
    narrative_text = "\n".join(f"*{label}:* {value}" for label, value in narrative_bits if value)
    if narrative_text:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": narrative_text}})

    blocks.append({"type": "divider"})
    return blocks
