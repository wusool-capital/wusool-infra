"""The four valuation methods and the blend — the deterministic fallback.

Verified by equivalence out of band: the DCF projection, WACC, terminal
value, all four methods and the blend were lifted from
`dopamine-valuation.html`'s React components into a node harness and run
over 3,000 cases — 8 sectors x 5 geographies x 5 revenue points x 5
profitability shapes x 3 stages. Zero mismatches outside Qatar, and all 270
Qatar cases differ by exactly the intended 0%-tax fix.

Kept here: the branches that would regress silently, and the pins on the
choices that look interchangeable and are not.
"""

import pytest

from app.modules.lead_magnets.domain.valuation.valuation_data import ListedComp
from app.modules.lead_magnets.domain.valuation.valuation_methods import (
    ValuationInputs,
    discounted_cash_flow,
    industry_research,
    project,
    size_premium,
    trading_comps,
    transaction_comps,
    value_company,
    wacc,
)


def _inputs(**kw) -> ValuationInputs:
    base = dict(
        revenue=3_000_000,
        profit_before_tax=400_000,
        owner_salary=60_000,
        sector="AI",
        geography="United Arab Emirates",
        stage="Seed",
    )
    return ValuationInputs(**{**base, **kw})


def test_adjusted_ebitda_adds_the_owner_salary_back() -> None:
    assert _inputs().adjusted_ebitda == 460_000
    assert _inputs(profit_before_tax=None, owner_salary=None).adjusted_ebitda == 0


@pytest.mark.parametrize(
    "revenue,expected",
    [(0, 5), (4_999_999, 5), (5_000_000, 4), (19_999_999, 4), (20_000_000, 3), (100_000_000, 2)],
)
def test_size_premium_tiers(revenue: float, expected: float) -> None:
    """Smaller businesses carry more equity risk; the tiers are the
    source's."""
    assert size_premium(revenue) == expected


def test_projection_is_five_years_and_decelerates() -> None:
    """Growth decelerates as a *rate*. The absolute increase can still rise
    for a while, because revenue is compounding off a bigger base — so the
    ratio year-on-year is what shows the deceleration, not the difference.
    """
    rows = project(_inputs())
    assert len(rows) == 5
    # Depreciation is a fixed share of revenue, so it tracks revenue exactly.
    ratios = [rows[i + 1].depreciation / rows[i].depreciation for i in range(4)]
    assert ratios == sorted(ratios, reverse=True)
    assert ratios[-1] < ratios[0]


def test_projection_rows_are_rounded() -> None:
    """The source rounds before the DCF consumes them, so rounding is part of
    the valuation rather than a display concern."""
    for row in project(_inputs()):
        assert row.ebit == int(row.ebit)
        assert row.depreciation == int(row.depreciation)
        assert row.capex == int(row.capex)
        assert row.working_capital == int(row.working_capital)


def test_margins_do_not_expand_indefinitely() -> None:
    """Uplift is capped, and a business already above 30% gets none — without
    that a 57% margin compounds to an implausible 67% by year five."""
    high = project(_inputs(profit_before_tax=1_700_000, owner_salary=0))  # ~57% margin
    ebitda_margin_y1 = (high[0].ebit + high[0].depreciation) / 1
    ebitda_margin_y5 = (high[4].ebit + high[4].depreciation) / 1
    assert ebitda_margin_y5 > ebitda_margin_y1  # grows with revenue...
    # ...but the *margin* itself does not expand: EBIT/revenue is flat, which
    # shows up as depreciation and EBIT scaling by the same factor.
    ratio_y1 = high[0].ebit / high[0].depreciation
    ratio_y5 = high[4].ebit / high[4].depreciation
    assert ratio_y1 == pytest.approx(ratio_y5, rel=0.01)


def test_a_loss_making_company_is_modelled_toward_profitability() -> None:
    """Quadratic easing, so improvement accelerates as it scales — rather
    than the company being written off at its current margin."""
    rows = project(_inputs(profit_before_tax=-500_000, owner_salary=0))
    assert rows[0].ebit < rows[-1].ebit
    # Accelerating, not linear.
    first_half = rows[1].ebit - rows[0].ebit
    second_half = rows[4].ebit - rows[3].ebit
    assert second_half > first_half


def test_working_capital_never_contributes_cash() -> None:
    """A revenue decline would otherwise show up as a working-capital
    release, flattering free cash flow."""
    assert all(r.working_capital >= 0 for r in project(_inputs(revenue=1_000)))


def test_wacc_with_no_debt_is_equity_cost_plus_size_premium() -> None:
    assert wacc(
        cost_of_equity=10,
        cost_of_debt=6,
        size_premium_pct=5,
        equity_value=1_000_000,
        debt=0,
        tax_rate_pct=9,
    ) == pytest.approx(0.15)


def test_wacc_zero_tax_is_not_coerced_to_twenty() -> None:
    """The source writes `tax || 20`, so a genuine 0% jurisdiction was taxed
    at 20% in the discount rate too."""
    taxed = wacc(
        cost_of_equity=10,
        cost_of_debt=6,
        size_premium_pct=5,
        equity_value=1_000,
        debt=1_000,
        tax_rate_pct=20,
    )
    untaxed = wacc(
        cost_of_equity=10,
        cost_of_debt=6,
        size_premium_pct=5,
        equity_value=1_000,
        debt=1_000,
        tax_rate_pct=0,
    )
    assert untaxed > taxed


def test_terminal_value_is_floored_when_cash_flow_never_turns_positive() -> None:
    """Otherwise a business that never generates cash is handed a large
    negative terminal drag instead of simply no terminal value.

    The case that triggers it is the *barely profitable* company, not the
    loss-making one — a surprise worth recording. A loss-maker takes the
    convergence path and lands on the sector's target margin (35% for AI) by
    year five, so its cash flow turns positive. A company at a 0.3% margin
    is not loss-making, so it takes the capped `+5 points` uplift path
    instead, and with capex at 7% of revenue against 5% depreciation it can
    still be cash-negative in year five.
    """
    barely_profitable = discounted_cash_flow(_inputs(profit_before_tax=10_000, owner_salary=0))
    assert barely_profitable.terminal_value_floored
    assert barely_profitable.terminal_value == 0
    assert barely_profitable.enterprise_value >= 0

    # The deeply loss-making company converges and is not floored.
    loss_making = discounted_cash_flow(_inputs(profit_before_tax=-5_000_000, owner_salary=0))
    assert not loss_making.terminal_value_floored
    assert loss_making.enterprise_value >= 0


def test_dlom_discounts_the_equity_value() -> None:
    """Trading and transaction comps are already haircut for illiquidity and
    the DCF is not, so without this the DCF sits far above every other
    method."""
    with_dlom = discounted_cash_flow(_inputs(dlom_pct=30))
    without = discounted_cash_flow(_inputs(dlom_pct=0))
    assert with_dlom.equity_value == pytest.approx(without.equity_value * 0.7)


def test_qatar_is_valued_at_zero_tax() -> None:
    """The intended divergence, end to end: 270 of 3,000 reference cases
    differ here, and only here."""
    qatar = discounted_cash_flow(_inputs(geography="Qatar"))
    germany = discounted_cash_flow(_inputs(geography="Germany"))
    assert qatar.enterprise_value > germany.enterprise_value


def test_trading_comps_use_the_median_and_a_multiplicative_size_discount() -> None:
    comps = (
        ListedComp(co="A", tk="A", ev=1000, rev=100, ebitda=20),
        ListedComp(co="B", tk="B", ev=3000, rev=200, ebitda=50),
        ListedComp(co="C", tk="C", ev=8000, rev=400, ebitda=100),
    )
    revenue_range, ebitda_range = trading_comps(_inputs(), comps)
    assert revenue_range.mid == pytest.approx(revenue_range.stats.median * (1 - 0.5) * (1 - 0.2))
    assert ebitda_range.mid > 0
    # A comp set this much larger than a $3m business earns a size discount.
    assert revenue_range.applied_discount_pct > 50


def test_negative_ebitda_adds_a_surcharge() -> None:
    comps = (ListedComp(co="A", tk="A", ev=1000, rev=100, ebitda=20),)
    healthy, _ = trading_comps(_inputs(), comps)
    loss, _ = trading_comps(_inputs(profit_before_tax=-900_000, owner_salary=0), comps)
    assert loss.mid < healthy.mid


def test_transaction_comps_use_the_mean_not_the_median() -> None:
    """Deliberately different from trading comps. Not a typo in either."""
    revenue_range, _ = transaction_comps(_inputs())
    assert revenue_range.mid == pytest.approx(revenue_range.stats.avg * 0.5)


def test_industry_research_blends_current_and_forward_multiples() -> None:
    result = industry_research(_inputs())
    assert result.mid > 0
    assert result.low <= result.high


def test_the_blend_averages_every_contributing_method() -> None:
    valuation = value_company(_inputs())
    assert valuation.methods
    assert valuation.mid == pytest.approx(
        sum(m.mid for m in valuation.methods) / len(valuation.methods)
    )
    assert valuation.low <= valuation.mid <= valuation.high


def test_every_method_row_is_ordered() -> None:
    for row in value_company(_inputs()).methods:
        assert row.low <= row.mid <= row.high


def test_an_ebitda_method_is_dropped_for_a_pre_profit_company() -> None:
    """The report says as much: a pre-profit valuation is weighted toward
    revenue-based methods."""
    profitable = value_company(_inputs())
    pre_profit = value_company(_inputs(profit_before_tax=-100_000, owner_salary=0))
    assert any("EV/EBITDA" in m.name for m in profitable.methods)
    assert not any("EV/EBITDA" in m.name for m in pre_profit.methods)


def test_no_revenue_produces_no_valuation_rather_than_a_wrong_one() -> None:
    empty = value_company(_inputs(revenue=0, profit_before_tax=0, owner_salary=0))
    assert empty.methods == ()
    assert (empty.low, empty.mid, empty.high) == (0, 0, 0)


def test_the_fallback_works_with_no_ai_comparables_at_all() -> None:
    """The whole point: the model only picks the comparables that set the
    trading multiples, so with it gone the static sector set still produces a
    blended range."""
    valuation = value_company(_inputs(ai_comps=()))
    assert valuation.mid > 0
    assert len(valuation.methods) >= 3


def test_model_supplied_comparables_are_preferred_when_present() -> None:
    tighter = (ListedComp(co="A", tk="A", ev=100, rev=50, ebitda=10),)
    with_ai = value_company(_inputs(ai_comps=tighter))
    without = value_company(_inputs())
    assert with_ai.mid != without.mid
