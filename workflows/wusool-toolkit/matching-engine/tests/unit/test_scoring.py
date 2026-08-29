"""Stage 1 filter + Stage 2 scoring unit tests (§9-14). Pure domain logic —
no database, no Bedrock, no Slack.
"""

from app.modules.matching.domain.scoring import (
    ScoringEngine,
    apply_structured_filters,
    needs_web_fallback,
    select_top_n,
)
from app.modules.matching.domain.value_objects import CandidateScore, DataConfidence
from app.modules.requirements.domain.value_objects import (
    HardRequirement,
    RequirementProfile,
    SoftPreference,
)
from app.modules.sellers.domain.value_objects import SellerCandidate
from app.shared.types import Money

CONFIDENCE_MULTIPLIERS = {"llm_extracted": 0.6, "llm_inferred": 0.4}


def _seller(
    seller_role_id: str = "s1",
    *,
    est_revenue: float | None = None,
    sector_focus: list[str] | None = None,
    geographic_focus: list[str] | None = None,
) -> SellerCandidate:
    return SellerCandidate(
        seller_role_id=seller_role_id,
        org_attio_id=f"org-{seller_role_id}",
        org_name=f"Seller {seller_role_id}",
        outreach_tier=None,
        relationship_status=None,
        appetite_signal=None,
        readiness_score=None,
        est_revenue=Money(amount=est_revenue, currency="USD") if est_revenue is not None else None,
        est_ebitda=None,
        valuation_low=None,
        valuation_mid=None,
        valuation_high=None,
        geographic_focus=geographic_focus or [],
        sector_focus=sector_focus or [],
    )


def _profile(hard: list[HardRequirement] | None = None) -> RequirementProfile:
    return RequirementProfile(
        hard_requirements=hard or [],
        soft_preferences=[],
        strategic_thesis=None,
        ideal_target_description=None,
        scoring_rubric={},
        data_confidence=1.0,
        generated_by_model="test-model",
        version=1,
    )


def test_populated_field_eliminates_failing_candidate() -> None:
    requirement = HardRequirement(
        criterion="minimum_revenue",
        value="50M",
        source="crm_field",
        confidence="high",
        human_confirmed=True,
    )
    passing = _seller("pass", est_revenue=80_000_000)
    failing = _seller("fail", est_revenue=30_000_000)

    survivors, skipped = apply_structured_filters(_profile([requirement]), [passing, failing])

    assert [s.seller_role_id for s in survivors] == ["pass"]
    assert skipped == []


def test_null_field_never_eliminates() -> None:
    """Missing-data pass-through (§9) is mandatory: NULL is normal."""
    requirement = HardRequirement(
        criterion="minimum_revenue",
        value="50M",
        source="crm_field",
        confidence="high",
        human_confirmed=True,
    )
    no_data = _seller("no_data", est_revenue=None)

    survivors, skipped = apply_structured_filters(_profile([requirement]), [no_data])

    assert [s.seller_role_id for s in survivors] == ["no_data"]
    assert skipped == [
        {"criterion": "minimum_revenue", "reason": "no_populated_field", "candidates_exempted": 1}
    ]


def test_unconfirmed_hard_requirement_never_eliminates() -> None:
    """§13: an unconfirmed LLM-extracted hard requirement must not silently
    hard-eliminate, even when a populated, failing seller field exists."""
    requirement = HardRequirement(
        criterion="minimum_revenue",
        value="50M",
        source="llm_extracted",
        confidence="low",
        human_confirmed=False,
    )
    failing_but_unconfirmed = _seller("would_fail", est_revenue=1)

    survivors, skipped = apply_structured_filters(
        _profile([requirement]), [failing_but_unconfirmed]
    )

    assert [s.seller_role_id for s in survivors] == ["would_fail"]
    assert skipped == [
        {
            "criterion": "minimum_revenue",
            "reason": "unconfirmed_llm_extraction",
            "candidates_exempted": 1,
        }
    ]


def test_unmapped_criterion_never_eliminates() -> None:
    requirement = HardRequirement(
        criterion="some_unheard_of_criterion",
        value="anything",
        source="crm_field",
        confidence="high",
        human_confirmed=True,
    )
    seller = _seller("s1")

    survivors, skipped = apply_structured_filters(_profile([requirement]), [seller])

    assert [s.seller_role_id for s in survivors] == ["s1"]
    assert skipped == [
        {
            "criterion": "some_unheard_of_criterion",
            "reason": "no_mapping",
            "candidates_exempted": 1,
        }
    ]


def test_sector_and_geography_filters() -> None:
    sector_req = HardRequirement(
        criterion="sector",
        value="fintech",
        source="crm_field",
        confidence="high",
        human_confirmed=True,
    )
    fintech_seller = _seller("fintech", sector_focus=["Fintech"])
    other_seller = _seller("other", sector_focus=["Healthcare"])

    survivors, _ = apply_structured_filters(_profile([sector_req]), [fintech_seller, other_seller])

    assert [s.seller_role_id for s in survivors] == ["fintech"]


def test_unconfirmed_hard_requirement_still_scored() -> None:
    """§13: it's not eliminated at Stage 1, but it must still count during
    Stage 2 scoring — this is what "strongly weighted criterion" means."""
    requirement = HardRequirement(
        criterion="minimum_revenue",
        value="50M",
        source="llm_extracted",
        confidence="low",
        human_confirmed=False,
    )
    failing = _seller("failing", est_revenue=1)
    engine = ScoringEngine(CONFIDENCE_MULTIPLIERS)

    result = engine.score("buyer-1", "failing", _profile([requirement]), failing)

    assert result.criteria[0].result == "Fail"
    assert result.criteria[0].data_backing == "crm_field"
    assert result.overall_score < 50.0  # the failing criterion pulls the score down


def test_data_confidence_formula() -> None:
    """sum(weight * multiplier) / sum(weight), only applicable criteria
    counted in the denominator's multiplier weighting per §12."""
    hard = HardRequirement(
        criterion="minimum_revenue",
        value="50M",
        source="crm_field",
        confidence="high",
        human_confirmed=True,
    )
    # A recognized criterion whose seller-side field just isn't populated —
    # distinct from an unrecognized criterion name (covered separately below).
    soft = SoftPreference(
        criterion="outreach_tier",
        value="tier-1",
        weight=1.0,
        source="llm_inferred",
        confidence="low",
    )
    profile = RequirementProfile(
        hard_requirements=[hard],
        soft_preferences=[soft],
        strategic_thesis=None,
        ideal_target_description=None,
        scoring_rubric={},
        data_confidence=1.0,
        generated_by_model="test-model",
        version=1,
    )
    candidate = _seller("s1", est_revenue=80_000_000)
    engine = ScoringEngine(CONFIDENCE_MULTIPLIERS)

    result = engine.score("buyer-1", "s1", profile, candidate)

    # hard: crm_field multiplier 1.0, weight 1.0 -> 1.0
    # soft: outreach_tier unpopulated -> unavailable, multiplier 0.0, weight 1.0 -> 0.0
    # (1.0*1.0 + 0.0*1.0) / (1.0 + 1.0) * 100 = 50.0
    assert result.confidence.value == 50.0
    assert result.confidence.applicable_criteria == 1
    assert result.confidence.total_criteria == 2


def test_unrecognized_criterion_excluded_from_scoring() -> None:
    """A criterion name the scoring engine doesn't recognize (never told to
    the extraction prompt, or invented anyway) must not silently dilute the
    score/confidence with a fabricated neutral value — it's recorded for
    audit but contributes no weight at all."""
    hard = HardRequirement(
        criterion="minimum_revenue",
        value="50M",
        source="crm_field",
        confidence="high",
        human_confirmed=True,
    )
    soft = SoftPreference(
        criterion="founder_led",
        value="True",
        weight=1.0,
        source="llm_extracted",
        confidence="medium",
    )
    profile = RequirementProfile(
        hard_requirements=[hard],
        soft_preferences=[soft],
        strategic_thesis=None,
        ideal_target_description=None,
        scoring_rubric={},
        data_confidence=1.0,
        generated_by_model="test-model",
        version=1,
    )
    candidate = _seller("s1", est_revenue=80_000_000)
    engine = ScoringEngine(CONFIDENCE_MULTIPLIERS)

    result = engine.score("buyer-1", "s1", profile, candidate)

    unrecognized = next(c for c in result.criteria if c.criterion == "founder_led")
    assert unrecognized.weight is None
    assert unrecognized.result == "Unrecognized"
    assert unrecognized.data_backing == "unavailable"
    # Only the recognized hard requirement counts toward the score/confidence.
    assert result.overall_score == 100.0
    assert result.confidence.value == 100.0
    assert result.confidence.total_criteria == 2
    assert result.confidence.applicable_criteria == 1


def test_select_top_n_ranks_by_score_only() -> None:
    def _score(seller_id: str, overall: float, confidence: float) -> CandidateScore:
        return CandidateScore(
            buyer_role_id="b1",
            seller_role_id=seller_id,
            overall_score=overall,
            confidence=DataConfidence(value=confidence, applicable_criteria=1, total_criteria=1),
        )

    scores = [_score("low_score_high_conf", 40.0, 95.0), _score("high_score_low_conf", 90.0, 20.0)]

    top = select_top_n(scores, 3)

    assert [s.seller_role_id for s in top] == ["high_score_low_conf", "low_score_high_conf"]


def test_select_top_n_returns_fewer_when_not_enough_candidates() -> None:
    """§14: never fabricate a third result."""
    scores = [
        CandidateScore(
            buyer_role_id="b1",
            seller_role_id="only_one",
            overall_score=70.0,
            confidence=DataConfidence(value=80.0, applicable_criteria=1, total_criteria=1),
        )
    ]

    top = select_top_n(scores, 3)

    assert len(top) == 1


def test_needs_web_fallback_on_empty_scores() -> None:
    assert needs_web_fallback([], min_score=50.0) is True


def test_needs_web_fallback_when_all_below_threshold() -> None:
    """The Falcon Partners case: three CRM candidates present, none good."""
    assert needs_web_fallback([50.0, 17.0, 17.0], min_score=51.0) is True


def test_needs_web_fallback_false_when_one_clears_threshold() -> None:
    assert needs_web_fallback([91.4, 17.0, 17.0], min_score=50.0) is False
