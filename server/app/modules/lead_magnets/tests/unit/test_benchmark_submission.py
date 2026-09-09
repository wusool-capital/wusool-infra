"""Benchmark orchestration, routing, quality gates and narrative.

Verified by equivalence out of band, not by hand: the live tool's own
`compute`, `route` and `quality` were run in node — `compute` against a
stubbed DOM — over 8,019 and 6,840 cases respectively and compared against
these modules. Zero mismatches after the rounding fix below.

Kept here: the rounding rule, the derivations where a blank field must not
read as a zero, the salary add-back, the implied-EV floor, and the routing
demotion.
"""

import pytest

from app.modules.lead_magnets.domain.benchmark import js_round
from app.modules.lead_magnets.domain.benchmark_narrative import flag_for
from app.modules.lead_magnets.domain.benchmark_routing import (
    MIN_COMPLETENESS,
    PRIORITY_COLD,
    PRIORITY_HOT,
    PRIORITY_WARM,
    headline_flag,
    quality,
    route,
    score_band,
)
from app.modules.lead_magnets.domain.benchmark_submission import (
    BenchmarkInputs,
    adjusted_ebitda,
    evaluate,
    metric_values,
)


def _sme(**kw) -> BenchmarkInputs:
    base = dict(
        mode="sme", peer_key="restaurant", revenue=3_000_000, headcount=40, email="a@acme.com"
    )
    return BenchmarkInputs(**{**base, **kw})


@pytest.mark.parametrize(
    "value,expected", [(42.5, 43), (43.5, 44), (0.5, 1), (-2.5, -2), (42.4, 42), (42.6, 43)]
)
def test_js_round_matches_javascript_not_python(value: float, expected: int) -> None:
    """JavaScript rounds a half away from zero; Python rounds a half to even.
    `round(42.5) == 42` in Python and `43` in JS — which is a benchmark score
    differing by a point from the report the visitor already saw. This
    accounted for 79 mismatches out of 8,019 reference cases.
    """
    assert js_round(value) == expected


def test_python_round_would_have_been_wrong() -> None:
    """Pinning the distinction, so nobody 'simplifies' js_round away."""
    assert round(42.5) == 42
    assert js_round(42.5) == 43


def test_salary_is_added_back_only_when_deducted() -> None:
    """The peer set's owners pay themselves differently, so reported profit
    is only comparable once the owner's salary is normalised out."""
    assert adjusted_ebitda(_sme(ebitda_reported=500_000, owner_salary=60_000)) == 500_000
    assert (
        adjusted_ebitda(_sme(ebitda_reported=500_000, owner_salary=60_000, salary_deducted=True))
        == 560_000
    )


def test_missing_ebitda_stays_none_after_add_back() -> None:
    assert adjusted_ebitda(_sme(owner_salary=60_000, salary_deducted=True)) is None


def test_ratios_are_none_not_zero_when_the_denominator_is_missing() -> None:
    """A blank field must drop out of the score, never rank at the bottom."""
    values = metric_values(_sme(revenue=None, headcount=None, prev_revenue=None))
    assert values["ebitda"] is None
    assert values["revEmp"] is None
    assert values["growth"] is None
    assert values["rent"] is None


def test_growth_needs_a_positive_prior_year() -> None:
    assert metric_values(_sme(prev_revenue=0))["growth"] is None
    assert metric_values(_sme(prev_revenue=2_000_000))["growth"] == pytest.approx(50.0)


def test_revenue_per_employee_is_in_thousands() -> None:
    """The dataset's anchors are thousands, so the derived value must be too
    or every ranking is out by 1000x."""
    assert metric_values(_sme(revenue=4_000_000, headcount=40))["revEmp"] == pytest.approx(100.0)


def test_rent_ratio_is_sme_only() -> None:
    assert metric_values(_sme(rent_cost=300_000))["rent"] == pytest.approx(10.0)
    tech = BenchmarkInputs(mode="tech", peer_key="seed", revenue=1_000_000, rent_cost=300_000)
    assert metric_values(tech)["rent"] is None


def test_tech_only_metrics_are_absent_in_sme_mode() -> None:
    values = metric_values(_sme(capital_raised=1_000_000))
    assert values["revScale"] is None
    assert values["capEff"] is None


def test_capital_efficiency_is_revenue_per_dollar_raised() -> None:
    tech = BenchmarkInputs(
        mode="tech", peer_key="seriesa", revenue=3_000_000, capital_raised=1_500_000
    )
    assert metric_values(tech)["capEff"] == pytest.approx(2.0)


def test_implied_ev_only_exists_in_startup_mode() -> None:
    assert evaluate(_sme()).implied_ev is None


def test_implied_ev_floors_forward_revenue_for_a_shrinking_company() -> None:
    """Without the 1.5x floor a shrinking company would project a lower
    forward revenue than it has today and price below its own trailing
    figure."""
    result = evaluate(
        BenchmarkInputs(mode="tech", peer_key="seriesa", revenue=1_000_000, prev_revenue=2_000_000)
    )
    assert result.implied_ev is not None
    assert result.implied_ev.forward_revenue == pytest.approx(1_500_000)


def test_implied_ev_repeats_the_growth_rate_when_growing() -> None:
    result = evaluate(
        BenchmarkInputs(mode="tech", peer_key="seriesa", revenue=2_000_000, prev_revenue=1_000_000)
    )
    assert result.implied_ev is not None
    assert result.implied_ev.forward_revenue == pytest.approx(4_000_000)
    assert result.implied_ev.low < result.implied_ev.mid < result.implied_ev.high


@pytest.mark.parametrize(
    "score,expected",
    [
        (100, "Top decile operator"),
        (78, "Top decile operator"),
        (77, "Above the pack"),
        (62, "Above the pack"),
        (45, "Solidly in the middle"),
        (28, "Below the peer median"),
        (0, "Early or under pressure"),
    ],
)
def test_score_band_thresholds(score: int, expected: str) -> None:
    assert score_band(score) == expected


def test_routing_demotes_a_thin_submission() -> None:
    """A high score off three answered fields is not a qualified lead."""
    hot = route(
        mode="sme",
        revenue_usd=9_000_000,
        years_active=20,
        data_completeness=80,
        percentiles={"ebitda": 10},
    )
    thin = route(
        mode="sme",
        revenue_usd=9_000_000,
        years_active=20,
        data_completeness=MIN_COMPLETENESS - 1,
        percentiles={"ebitda": 10},
    )
    assert hot.priority == PRIORITY_HOT
    assert thin.priority == PRIORITY_WARM
    assert "Demoted" in thin.reason


def test_routing_falls_back_to_revenue_then_cold() -> None:
    warm = route(
        mode="sme", revenue_usd=600_000, years_active=2, data_completeness=80, percentiles={}
    )
    cold = route(
        mode="sme", revenue_usd=100_000, years_active=2, data_completeness=80, percentiles={}
    )
    assert warm.priority == PRIORITY_WARM
    assert cold.priority == PRIORITY_COLD
    assert cold.reason == "No routing trigger"


def test_quality_rejects_without_revenue_or_headcount() -> None:
    common = dict(
        email="a@acme.com", gross_margin_pct=None, ebitda_adjusted_usd=None, prev_revenue_usd=None
    )
    assert quality(mode="sme", revenue_usd=None, headcount=10, **common).check == "Rejected"
    assert quality(mode="sme", revenue_usd=1_000_000, headcount=None, **common).check == "Rejected"


def test_quality_flags_operating_profit_above_gross_profit() -> None:
    """Arithmetically impossible; the 2-point tolerance absorbs rounding in
    self-reported figures."""
    result = quality(
        mode="sme",
        email="a@acme.com",
        revenue_usd=1_000_000,
        headcount=5,
        gross_margin_pct=10,
        ebitda_adjusted_usd=300_000,
        prev_revenue_usd=None,
    )
    assert result.check == "Flagged - implausible"


def test_quality_loss_floor_is_looser_for_tech() -> None:
    """Loss-making is normal in tech, not in a trading business."""
    args = dict(
        email="a@acme.com",
        revenue_usd=1_000_000,
        headcount=5,
        gross_margin_pct=None,
        ebitda_adjusted_usd=-2_000_000,
        prev_revenue_usd=None,
    )
    assert quality(mode="sme", **args).check == "Flagged - implausible"
    assert quality(mode="tech", **args).check == "Passed"


def test_quality_flags_free_email_at_scale() -> None:
    result = quality(
        mode="sme",
        email="founder@gmail.com",
        revenue_usd=6_000_000,
        headcount=20,
        gross_margin_pct=None,
        ebitda_adjusted_usd=None,
        prev_revenue_usd=None,
    )
    assert result.check == "Flagged - free email at scale"


def test_quality_never_auto_includes_in_the_dataset() -> None:
    """The auto-checks triage; a human approves a record in."""
    result = quality(
        mode="sme",
        email="a@acme.com",
        revenue_usd=1_000_000,
        headcount=5,
        gross_margin_pct=None,
        ebitda_adjusted_usd=None,
        prev_revenue_usd=None,
    )
    assert result.check == "Passed"
    assert result.include_in_benchmark is False


def test_headline_flag_names_the_weakest_metric() -> None:
    assert (
        headline_flag({"ebitda": 70, "conc": 12.4, "gm": 55}) == "Weakest: conc at 12th percentile"
    )
    assert headline_flag({"ebitda": None}) == ""


def test_flags_only_appear_at_the_extremes() -> None:
    """A metric in the middle says nothing worth a paragraph, so the report
    stays short rather than padded with 'you are about average'."""
    result = evaluate(_sme(gross_margin_pct=100, top_customer_pct=95))
    assert result.flags
    assert all(f.percentile >= 68 or f.percentile < 40 for f in result.flags)


def test_flag_body_substitutes_every_placeholder() -> None:
    result = evaluate(_sme(gross_margin_pct=100))
    flag = next(f for f in result.flags if f.tone == "good")
    assert "{" not in flag.body and "}" not in flag.body


def test_flags_are_ordered_worst_first() -> None:
    result = evaluate(_sme(gross_margin_pct=100, top_customer_pct=95, recurring_pct=95))
    percentiles = [f.percentile for f in result.flags]
    assert percentiles == sorted(percentiles)


def test_evaluate_reports_coverage_alongside_the_score() -> None:
    sparse = evaluate(_sme(gross_margin_pct=None, top_customer_pct=None, recurring_pct=None))
    full = evaluate(
        _sme(
            gross_margin_pct=35,
            top_customer_pct=20,
            recurring_pct=40,
            prev_revenue=2_500_000,
            ebitda_reported=400_000,
            rent_cost=200_000,
        )
    )
    assert full.data_completeness > sparse.data_completeness
    assert full.metrics_covered > sparse.metrics_covered
    assert full.metrics_total == 7


def test_flag_for_returns_none_on_an_unranked_metric() -> None:
    result = evaluate(_sme(gross_margin_pct=None))
    assert flag_for(result.metrics["gm"], peer_label="restaurants", mode="sme") is None
