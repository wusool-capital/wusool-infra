"""LLM narrative uses "~$2M" to mean "approximately $2M" — Slack's mrkdwn
parses a `~..~` span as strikethrough, silently striking out everything
between two such tildes in the same message. Regression coverage for the
fix: swap tildes for the actual approximation sign before rendering.
"""

from app.modules.matching.application.use_cases import MatchRunResult, ShortlistedResult
from app.modules.matching.schemas import MatchAnalysis, MatchResultRead
from app.modules.slack.views.full_analysis import build_full_analysis_blocks
from app.modules.slack.views.match_result import build_match_result_blocks
from app.modules.slack.views.mrkdwn import sanitize_mrkdwn


def test_sanitize_replaces_tildes_with_approximation_sign() -> None:
    text = "estimated revenue of AED 7.5m (~$2m USD) and EBITDA of ~AED 1.65m ($450k USD)"

    assert "~" not in sanitize_mrkdwn(text)
    assert "≈" in sanitize_mrkdwn(text)


def test_match_result_rationale_has_no_tildes() -> None:
    result = MatchRunResult(
        run_id="run-1",
        status="GENERATED",
        buyer_org_name="Naser Sultan",
        results=[
            ShortlistedResult(
                match_result_id="mr-1",
                rank=1,
                seller_role_id="seller-1",
                seller_org_name="Mansouri Dental Group LLC",
                match_score=79.0,
                data_confidence=59.0,
                why_it_matches="estimated revenue of AED 7.5m (~$2m USD) and ~AED 1.65m EBITDA",
                why_chosen_over_alternatives=None,
                recommended_pitch=None,
                risks_and_gaps=None,
            )
        ],
    )

    blocks = build_match_result_blocks(result)
    rendered = "\n".join(
        b["text"]["text"] for b in blocks if b.get("type") == "section" and "text" in b
    )

    assert "~" not in rendered


def test_full_analysis_narrative_has_no_tildes() -> None:
    import uuid

    run_id = uuid.uuid4()
    run = MatchResultRead(id=uuid.uuid4(), run_id=run_id, status="GENERATED")
    candidate = MatchResultRead(
        id=uuid.uuid4(),
        run_id=run_id,
        rank=1,
        seller_attio_id="seller-1",
        seller_org_name="Al-Farsi Trading LLC",
        match_score=59,
        data_confidence=100,
        status="PENDING_REVIEW",
        risks_and_gaps="Revenue of ~$408k USD and ~AED 300k EBITDA is well below the floor.",
    )
    analysis = MatchAnalysis(run=run, candidates=[candidate], scores=[])

    blocks = build_full_analysis_blocks(analysis)
    rendered = "\n".join(b["text"]["text"] for b in blocks if b.get("type") == "section")

    assert "~" not in rendered
