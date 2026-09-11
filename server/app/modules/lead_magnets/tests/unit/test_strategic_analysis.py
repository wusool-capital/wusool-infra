"""`/analyze`'s deterministic fallback (pros/cons/insights only).

Verified by equivalence out of band: `generateStrategicAnalysis` was
extracted from `dopamine-valuation.html` into a Node harness, run over 113
generated cases spanning every one of the 19 regex signals, every margin
boundary, and every fundraise/geography/sector combination, and compared
against this module. 0 mismatches. The cases here are a fixed subset of
that run, encoded as permanent assertions — this file has no Node
dependency at test time.
"""

from app.modules.lead_magnets.domain.valuation.strategic_analysis import (
    generate_strategic_analysis,
)


def test_pros_cons_and_insights_are_always_the_full_count() -> None:
    """The fallback lists exist so a short list is never possible, even for
    a description with no signals at all."""
    result = generate_strategic_analysis(
        company="", description="", sector="", revenue=0, ebitda=0, geography=""
    )
    assert len(result.pros) == 3
    assert len(result.cons) == 3
    assert len(result.insights) == 2


def test_matched_pool_entries_come_before_fallbacks_in_pool_order() -> None:
    """A description matching only one real signal still fills to 3 pros —
    two of them fallbacks — and the matched one leads, matching the
    original's `.filter().slice(0,3)` (earliest matches, not "best")."""
    result = generate_strategic_analysis(
        company="Acme",
        description="Offers a recurring monthly plan for ongoing access.",
        sector="",
        revenue=0,
        ebitda=0,
        geography="",
    )
    assert (
        result.pros[0].title
        == "Recurring revenue model converts transactions into a predictable annuity stream"
    )
    assert result.pros[1].title == "Clear value proposition in a defined and growing market"
    assert result.pros[2].title == "Brand identity that compounds in value with scale"


def test_heritage_and_premium_together_beats_either_alone() -> None:
    """Pool order matters: `isPremium&&hasBrandHeritage` is checked before
    either single-signal variant, so a description matching both gets the
    combined pro, not the premium-only one."""
    result = generate_strategic_analysis(
        company="Acme",
        description="A premium, heritage brand crafted for generations.",
        sector="",
        revenue=0,
        ebitda=0,
        geography="",
    )
    assert result.pros[0].title == "Heritage craft narrative creates durable brand defensibility"


def test_negative_margin_produces_the_negative_margin_insight() -> None:
    result = generate_strategic_analysis(
        company="Acme", description="", sector="", revenue=1000, ebitda=-100, geography=""
    )
    assert (
        result.insights[0].title
        == "Path to profitability is the highest-priority near-term milestone"
    )


def test_margin_exactly_zero_produces_no_margin_insight() -> None:
    """A pre-existing gap in the original, replicated rather than fixed:
    `margin<0`, `0<margin<15` and `margin>=15` between them cover every
    real number except exactly 0."""
    result = generate_strategic_analysis(
        company="Acme", description="", sector="", revenue=1000, ebitda=0, geography=""
    )
    assert not any("margin" in i.title.lower() for i in result.insights)


def test_low_margin_insight_interpolates_the_rounded_percentage() -> None:
    result = generate_strategic_analysis(
        company="Acme", description="", sector="", revenue=1000, ebitda=100, geography=""
    )
    assert "10%" in result.insights[0].body


def test_gcc_geography_adds_its_own_insight() -> None:
    result = generate_strategic_analysis(
        company="Acme",
        description="",
        sector="",
        revenue=6_000_000,
        ebitda=-100,
        geography="Saudi Arabia",
    )
    titles = [i.title for i in result.insights]
    assert "GCC-first depth before multi-region expansion" in titles


def test_no_raise_and_low_revenue_adds_pre_fundraise_insight() -> None:
    result = generate_strategic_analysis(
        company="Acme",
        description="",
        sector="",
        revenue=1_000_000,
        ebitda=100_000,
        geography="",
        raised=False,
    )
    titles = [i.title for i in result.insights]
    assert "Institutional fundraising readiness: build the metrics story now" in titles


def test_raised_seed_or_series_a_under_ten_million_adds_series_b_insight() -> None:
    result = generate_strategic_analysis(
        company="Acme",
        description="",
        sector="",
        revenue=9_000_000,
        ebitda=900_000,
        geography="",
        raised=True,
        stage="series a",
    )
    titles = [i.title for i in result.insights]
    assert "Series B readiness requires demonstrating repeatability at scale" in titles


def test_b2b_sector_above_two_million_revenue_adds_nrr_insight() -> None:
    result = generate_strategic_analysis(
        company="Acme",
        description="",
        sector="SaaS",
        revenue=6_000_000,
        ebitda=600_000,
        geography="",
    )
    titles = [i.title for i in result.insights]
    assert "Net revenue retention expansion delivers higher ROI than new logo acquisition" in titles


def test_travel_fashion_or_personalised_signal_adds_data_insight() -> None:
    result = generate_strategic_analysis(
        company="Acme",
        description="A travel and fashion lifestyle brand.",
        sector="",
        revenue=6_000_000,
        ebitda=1_200_000,
        geography="",
    )
    titles = [i.title for i in result.insights]
    assert "Customer data infrastructure is the core long-term strategic asset" in titles


def test_no_signals_at_all_falls_back_to_the_two_generic_insights() -> None:
    """`margin===0` (the same gap as above) plus `raised=True` with an
    empty `stage` avoids both fundraise conditions too — the only
    combination that leaves the insight pool genuinely empty."""
    result = generate_strategic_analysis(
        company="Acme",
        description="",
        sector="",
        revenue=1000,
        ebitda=0,
        geography="",
        raised=True,
        stage="",
    )
    titles = [i.title for i in result.insights]
    assert titles == [
        "Strategic distribution partnerships can accelerate the growth trajectory",
        "Operational excellence as a compounding competitive differentiator",
    ]


def test_empty_company_and_sector_fall_back_to_defaults() -> None:
    """`co=gate.companyName||"The company"` in the original — an empty
    string must not appear verbatim in the copy."""
    result = generate_strategic_analysis(
        company="", description="", sector="", revenue=0, ebitda=0, geography=""
    )
    assert "The company" in result.pros[0].body
