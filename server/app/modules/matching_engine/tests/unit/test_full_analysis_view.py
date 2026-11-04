"""View Full Analysis Block Kit rendering: seller org names (not raw
attio_ids) and rounded scores (not raw Decimal/float precision garbage).
"""

import uuid
from decimal import Decimal

from app.modules.matching_engine.api.matching import MatchAnalysis, MatchResultRead
from app.modules.matching_engine.api.slack.views.full_analysis import build_full_analysis_blocks


def _analysis() -> MatchAnalysis:
    run_id = uuid.uuid4()
    run = MatchResultRead(id=uuid.uuid4(), run_id=run_id, status="GENERATED")
    candidate = MatchResultRead(
        id=uuid.uuid4(),
        run_id=run_id,
        rank=1,
        seller_attio_id="test-org-seller-2",
        seller_org_name="PaySecure Holdings",
        match_score=Decimal("52.630000000000002557953848736360669136047363281250"),
        data_confidence=Decimal("100"),
        status="PENDING_REVIEW",
    )
    return MatchAnalysis(run=run, candidates=[candidate], scores=[])


def _rendered_text(blocks) -> str:
    dicts = [b.to_dict() for b in blocks]
    return "\n".join(b["text"]["text"] for b in dicts if b.get("type") == "section")


def test_candidate_header_shows_org_name_not_attio_id() -> None:
    text = _rendered_text(build_full_analysis_blocks(_analysis()))

    assert "PaySecure Holdings" in text
    assert "test-org-seller-2" not in text


def test_candidate_header_rounds_score_not_raw_decimal() -> None:
    text = _rendered_text(build_full_analysis_blocks(_analysis()))

    assert "52.630000000000002557953848736360669136047363281250" not in text
    assert "53/100" in text or "52/100" in text


def test_bulleted_narrative_starts_on_its_own_line_with_slack_bullets() -> None:
    analysis = _analysis()
    analysis.candidates[0].risks_and_gaps = "- Ticket: unknown\n- Geography: blank"

    text = _rendered_text(build_full_analysis_blocks(analysis))

    assert "*Risks and gaps:*\n• Ticket: unknown\n• Geography: blank" in text


def test_single_sentence_narrative_stays_inline() -> None:
    analysis = _analysis()
    analysis.candidates[0].recommended_pitch = "Lead with the cybersecurity angle."

    text = _rendered_text(build_full_analysis_blocks(analysis))

    assert "*Recommended pitch:* Lead with the cybersecurity angle." in text
