"""The ported readiness questionnaire, advisory rules and prompts.

The expected strings here are copied from the live `buildAdvisoryContent`
and `buildPrompt` in `dopamine-readiness-score.html`. They are the regression
net for the port: these values land in Attio text fields a human reads, and
the score/band drive `seller_roles.readiness_score`/`readiness_band`.
"""

import pytest

from app.modules.lead_magnets.domain.prompts import (
    readiness_advisory_prompt,
    readiness_score_prompt,
)
from app.modules.lead_magnets.domain.readiness import (
    AdvisoryContent,
    ReadinessAnswers,
    attio_band,
    build_advisory_content,
    merge_advisory,
    revenue_range_midpoint_usd,
)

# Every scored question at its best answer — no rule should fire.
_CLEAN = ReadinessAnswers(
    q1=3, q2=3, q3=3, q4=3, q5=3, q6=3, q7=3, q8=3, q9=3, q10=3, q11=3, q12=3, q13=3
)


def test_clean_answers_produce_no_referral_and_no_note() -> None:
    assert build_advisory_content(_CLEAN) == AdvisoryContent(referral=None, advisory_note=None)


def test_unanswered_questions_fire_nothing() -> None:
    """A partially completed form must not be read as a zero — `q2 == 0` is
    the hard DEAL RISK flag, and `None` is not that."""
    assert build_advisory_content(ReadinessAnswers()) == AdvisoryContent()


@pytest.mark.parametrize("q1", [0, 1])
def test_weak_financials_refer_to_audit(q1: int) -> None:
    result = build_advisory_content(ReadinessAnswers(q1=q1))
    assert result.referral == "Audit / accounting partner (UAE Freezone Service Providers list)"
    assert result.advisory_note == (
        "Financial statements not accountant-prepared. "
        "Refer for audit/accounting before buyer process."
    )


def test_q1_at_two_does_not_refer() -> None:
    """Accountant-prepared but unaudited is the boundary: the live rule is
    `<= 1`, so 2 must produce nothing."""
    assert build_advisory_content(ReadinessAnswers(q1=2)) == AdvisoryContent()


def test_customer_concentration_over_half_is_a_hard_flag() -> None:
    result = build_advisory_content(ReadinessAnswers(q2=0))
    assert result.advisory_note == (
        "DEAL RISK: Single customer exceeds 50% of revenue. "
        "High buyer concern - do not refer until concentration is addressed."
    )
    # A note, never a referral — there is no partner who fixes concentration.
    assert result.referral is None


def test_moderate_concentration_is_a_softer_note() -> None:
    assert build_advisory_content(ReadinessAnswers(q2=1)).advisory_note == (
        "Customer concentration 30-50%. Moderate risk - confirm diversification plan on first call."
    )


def test_ip_in_personal_name_versus_pending_transfer() -> None:
    """Both fire a referral, with different wording — `q12 == 2` is the only
    rule in the set that treats a mid-range answer as actionable."""
    personal = build_advisory_content(ReadinessAnswers(q12=0))
    pending = build_advisory_content(ReadinessAnswers(q12=2))
    assert personal.referral == "IP / legal partner (key assets or brand held in personal name)"
    assert pending.referral == (
        "IP / legal partner (some assets pending formal transfer to company)"
    )
    assert build_advisory_content(ReadinessAnswers(q12=3)) == AdvisoryContent()


def test_multiple_referrals_join_with_semicolons_and_notes_with_pipes() -> None:
    """The separators are what the live code writes into the Attio text
    fields, so they are part of the contract, not formatting."""
    result = build_advisory_content(ReadinessAnswers(q1=0, q3=0, q10=0, q12=0, q2=0))
    assert result.referral is not None
    assert result.referral.count("; ") == 3
    assert result.advisory_note is not None
    assert result.advisory_note.count(" | ") == 4
    assert result.advisory_note.startswith("Financial statements not accountant-prepared.")


def test_merge_advisory_keeps_the_rules_note() -> None:
    """The live code assigns the model's note over the deterministic one, so
    a DEAL RISK flag vanishes whenever the prose does not repeat it."""
    rules = build_advisory_content(ReadinessAnswers(q2=0))
    merged = merge_advisory(rules, "Founder is realistic about valuation.")

    assert merged.advisory_note is not None
    assert merged.advisory_note.startswith("DEAL RISK:")
    assert merged.advisory_note.endswith("Founder is realistic about valuation.")


def test_merge_advisory_never_takes_the_referral_from_the_model() -> None:
    rules = AdvisoryContent(referral="Audit / accounting partner", advisory_note=None)
    assert merge_advisory(rules, "some prose").referral == "Audit / accounting partner"


def test_merge_advisory_with_no_model_note_is_the_rules_unchanged() -> None:
    rules = build_advisory_content(ReadinessAnswers(q2=0))
    assert merge_advisory(rules, None) == rules
    assert merge_advisory(rules, "") == rules


@pytest.mark.parametrize(
    "band,expected",
    [
        ("Not Ready", "Early"),
        ("Early Stage", "Early"),
        ("Getting There", "Developing"),
        ("Nearly Ready", "Sale Ready"),
        ("Exit Ready", "Market Ready"),
        ("  exit ready  ", "Market Ready"),
        (None, None),
    ],
)
def test_attio_band_translation(band, expected) -> None:
    """Writing the prompt's own wording to Attio would miss the select option
    and fail the write."""
    assert attio_band(band) == expected


def test_unknown_band_passes_through() -> None:
    assert attio_band("Somehow New") == "Somehow New"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Under $1m", 500_000.0),
        ("$1m – $5m", 3_000_000.0),
        ("$50m+", 75_000_000.0),
        ("nonsense", None),
        (None, None),
    ],
)
def test_revenue_range_midpoint_is_usd(value, expected) -> None:
    """USD, unconverted — the form collects a band, not a figure."""
    assert revenue_range_midpoint_usd(value) == expected


def test_score_prompt_carries_every_answer_and_the_free_text() -> None:
    answers = ReadinessAnswers(
        q1=3, q2=0, q13=2, q14="Recurring GCC contracts", q15="Could not hire fast enough"
    )
    prompt = readiness_score_prompt(
        founder="Dana",
        business="Acme Fit-Out",
        sector="Contracting",
        revenue_range="$1m – $5m",
        country="UAE",
        answers=answers,
    )

    assert "Financial statements quality: 3/3" in prompt
    assert "Customer concentration risk: 0/3" in prompt
    assert "Buyer proposition clarity: 2/3" in prompt
    assert '"Recurring GCC contracts"' in prompt
    assert '"Could not hire fast enough"' in prompt
    # Unanswered must not read as zero.
    assert "Management team strength: not answered/3" in prompt
    # The response contract the page renders.
    assert '"insight"' in prompt
    assert '"recommendations"' in prompt


def test_advisory_prompt_drops_task_2_and_adds_the_free_text() -> None:
    """The referral is computed, not asked for — asking a model to re-derive
    it from conditions we already evaluate is where drift comes from."""
    prompt = readiness_advisory_prompt(
        company="Acme",
        sector="Contracting",
        revenue_range="$1m – $5m",
        score=62,
        band="Getting There",
        answers=ReadinessAnswers(q1=0, q2=0, q14="Strong brand", q15="Cash flow"),
    )

    assert "TASK 2" not in prompt
    assert "RECOMMENDED REFERRAL" not in prompt
    assert "recommendedReferral" not in prompt
    assert "IN THEIR OWN WORDS" in prompt
    assert '"Strong brand"' in prompt
    assert '"Cash flow"' in prompt
    # Answer labels, not bare integers — the option text is what carries meaning.
    assert "Internal spreadsheets only" in prompt
    assert "One customer >50% of revenue" in prompt
    assert "62/100 (Getting There)" in prompt
