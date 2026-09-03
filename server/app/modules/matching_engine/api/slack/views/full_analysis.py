"""View Full Analysis (§21) — rendered entirely from persisted data
(`MatchAnalysis`), never re-running Bedrock. Block Kit builders only.

Slack rejects a whole `chat.postEphemeral`/`chat.postMessage` call
(`invalid_blocks`) if any single section's `text` exceeds 3000 characters —
confirmed live: a real reasoning call's combined narrative hit 3150 chars.
Each narrative field gets its own block (truncated defensively) instead of
concatenating them into one, so a single verbose LLM field can't blow the
whole message.
"""

from slack_sdk.models.blocks import Block, DividerBlock, HeaderBlock, SectionBlock

from app.modules.matching_engine.api.matching import (
    MatchAnalysis,
    MatchResultRead,
    MatchScoreRead,
)
from app.modules.notifications import sanitize_mrkdwn

_MAX_SECTION_TEXT = 2900


def _truncate(text: str) -> str:
    if len(text) <= _MAX_SECTION_TEXT:
        return text
    return text[: _MAX_SECTION_TEXT - 1] + "…"


def _section(text: str) -> SectionBlock:
    return SectionBlock(text=_truncate(sanitize_mrkdwn(text)))


def build_full_analysis_blocks(analysis: MatchAnalysis) -> list[Block]:
    blocks: list[Block] = []
    profile = analysis.run.requirement_profile

    blocks.append(HeaderBlock(text="Buyer & Mandate"))
    thesis = (profile.strategic_thesis if profile else None) or "Unknown"
    ideal_target = (profile.ideal_target_description if profile else None) or "Unknown"
    hard_reqs = profile.hard_requirements if profile else []
    hard_req_lines = (
        "\n".join(
            f"• {r.criterion}: {r.value or 'Unknown'} ({r.source}, confirmed={r.human_confirmed})"
            for r in hard_reqs
        )
        or "None extracted."
    )
    blocks.append(
        _section(
            f"*Strategic thesis:* {thesis}\n"
            f"*Ideal target:* {ideal_target}\n"
            f"*Hard requirements:*\n{hard_req_lines}"
        )
    )
    blocks.append(DividerBlock())

    blocks.append(HeaderBlock(text="Top Matches"))
    scores_by_id = {s.id: s for s in analysis.scores}
    for candidate in sorted(analysis.candidates, key=lambda c: c.rank or 0):
        blocks.extend(_candidate_blocks(candidate, scores_by_id))

    return blocks


def _candidate_blocks(candidate: MatchResultRead, scores_by_id: dict) -> list[Block]:
    seller_name = candidate.seller_org_name or candidate.seller_attio_id or "Unknown"
    score_text = f"{candidate.match_score:.0f}" if candidate.match_score is not None else "Unknown"
    confidence_text = (
        f"{candidate.data_confidence:.0f}" if candidate.data_confidence is not None else "Unknown"
    )
    blocks: list[Block] = [
        _section(
            f"*{candidate.rank}. {seller_name}* — "
            f"Match score: {score_text}/100, Data confidence: {confidence_text}/100\n"
            f"Status: {candidate.status}"
        )
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
        blocks.append(_section(criteria_lines))

    # Each narrative field is its own block (not concatenated) — a single
    # verbose LLM-generated field can't blow the 3000-char section limit for
    # the whole message the way one combined block did.
    narrative_bits = [
        ("Why it matches", score.reasoning if score else None),
        ("Why chosen over alternatives", candidate.why_chosen_over_alternatives),
        ("Recommended pitch", candidate.recommended_pitch),
        ("Risks and gaps", candidate.risks_and_gaps),
    ]
    for label, value in narrative_bits:
        if value:
            blocks.append(_section(f"*{label}:* {value}"))

    blocks.append(DividerBlock())
    return blocks
