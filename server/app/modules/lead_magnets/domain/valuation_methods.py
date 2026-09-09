"""The four valuation methods and the blend — the valuation tool's
deterministic fallback. Pure.

This is what keeps the visitor getting a real valuation when the model
fails: the AI only picks the comparable companies that set the trading
multiples, so with it gone the DCF, transaction comps and industry research
still produce a blended range from static sector data.

Ported from `dopamine-valuation.html`'s `DCFModule`, `TradingComps`,
`TransactionComps`, `IndustryResearch` and `ValuationSummary`. Details that
look incidental and are not:

- The projection rows are **rounded to whole units** before the DCF consumes
  them, so rounding is part of the result rather than a display concern, and
  it uses JavaScript's half-away-from-zero rule (`js_round`).
- Trading comps take the **median** multiple, transaction comps the
  **mean**. Not a typo in either.
- The size discount and the user haircut compose **multiplicatively** in
  trading comps and **additively** in transaction comps.
- Terminal value is floored at zero when the final year's free cash flow is
  negative, so a business that never turns cash-positive is not handed a
  large negative terminal drag.
- The blend is an unweighted mean across whichever methods produced a
  positive mid, and each row plus the final result is sorted so
  low <= mid <= high.

One divergence from the source, consistent with `valuation.tax_rate`: a 0%
tax jurisdiction stays 0%. The original writes `tax || 20`, so Qatar and
Bahrain were silently taxed at 20% here too.
"""

from dataclasses import dataclass, field

from app.modules.lead_magnets.domain.benchmark import js_round
from app.modules.lead_magnets.domain.valuation import (
    Stats,
    growth_benchmark,
    match_transactions,
    match_vc_rounds,
    stats,
    tax_rate,
    wacc_benchmark,
)
from app.modules.lead_magnets.domain.valuation_data import ListedComp

# Growth decelerates over the projection: flat for two years, then easing off.
_DECELERATION = (1.0, 1.0, 0.8, 0.65, 0.5)
_PROJECTION_YEARS = 5

# Discount for lack of marketability. Trading and transaction comps are
# already haircut for illiquidity and the DCF was not, so without this the
# DCF sat far above every other method.
_DEFAULT_DLOM_PCT = 30.0

# Defaults when no Damodaran industry matches.
_DEFAULT_COST_OF_EQUITY = 12.0
_DEFAULT_COST_OF_DEBT = 6.0
_DEFAULT_SIZE_PREMIUM = 3.0

# Margins mean-revert rather than expanding indefinitely.
_MAX_MARGIN_UPLIFT_PCT = 5.0
_MARGIN_CEILING_PCT = 45.0
_NO_UPLIFT_ABOVE_MARGIN_PCT = 30.0

_NEGATIVE_EBITDA_SURCHARGE_PCT = 20.0
_DEFAULT_HAIRCUT_PCT = 50.0


@dataclass(frozen=True)
class ValuationInputs:
    revenue: float
    profit_before_tax: float | None = None
    owner_salary: float | None = None
    sector: str | None = None
    geography: str | None = None
    stage: str | None = None
    cash: float = 0.0
    debt: float = 0.0
    dlom_pct: float = _DEFAULT_DLOM_PCT
    haircut_revenue_pct: float = _DEFAULT_HAIRCUT_PCT
    haircut_ebitda_pct: float = _DEFAULT_HAIRCUT_PCT
    # The model's comparables when it produced any; the static sector set
    # is used when it did not.
    ai_comps: tuple[ListedComp, ...] = field(default_factory=tuple)

    @property
    def adjusted_ebitda(self) -> float:
        """Profit before tax with the owner's salary added back — the figure
        every method values off."""
        return (self.profit_before_tax or 0) + (self.owner_salary or 0)


@dataclass(frozen=True)
class ProjectionYear:
    label: int
    ebit: float
    depreciation: float
    capex: float
    working_capital: float


@dataclass(frozen=True)
class DcfResult:
    enterprise_value: float
    equity_value: float
    wacc: float
    terminal_value: float
    terminal_value_floored: bool
    sum_discounted_fcf: float
    projection: tuple[ProjectionYear, ...]


@dataclass(frozen=True)
class MultipleRange:
    low: float
    mid: float
    high: float
    stats: Stats
    applied_discount_pct: float


@dataclass(frozen=True)
class MethodRow:
    name: str
    low: float
    mid: float
    high: float


@dataclass(frozen=True)
class Valuation:
    low: float
    mid: float
    high: float
    methods: tuple[MethodRow, ...]
    dcf: DcfResult | None


def size_premium(revenue: float) -> float:
    """Smaller businesses carry more equity risk. Tiers from the source."""
    if revenue < 5_000_000:
        return 5.0
    if revenue < 20_000_000:
        return 4.0
    if revenue < 100_000_000:
        return 3.0
    return 2.0


def project(inputs: ValuationInputs) -> tuple[ProjectionYear, ...]:
    """A five-year EBIT projection from the sector's growth benchmark.

    A loss-making company is modelled on a path to profitability with
    quadratic easing, so improvement accelerates as it scales, rather than
    being written off at its current margin.
    """
    growth = growth_benchmark(inputs.sector)
    revenue = inputs.revenue or 0
    base_margin = (inputs.adjusted_ebitda / revenue) * 100 if revenue > 0 else 5.0
    target_margin = max(growth.ebit_margin_improvement * 5 + 5, 15)
    loss_making = base_margin < 0

    rows: list[ProjectionYear] = []
    previous_revenue = revenue
    year = _current_year()

    for i in range(_PROJECTION_YEARS):
        projected_revenue = previous_revenue * (
            1 + (growth.revenue_growth / 100) * _DECELERATION[i]
        )
        if loss_making:
            eased = ((i + 1) / _PROJECTION_YEARS) ** 2
            projected_margin = base_margin + (target_margin - base_margin) * eased
        else:
            uplift = (
                0.0
                if base_margin >= _NO_UPLIFT_ABOVE_MARGIN_PCT
                else min(growth.ebit_margin_improvement * (i + 1), _MAX_MARGIN_UPLIFT_PCT)
            )
            projected_margin = min(base_margin + uplift, _MARGIN_CEILING_PCT)

        projected_ebitda = projected_revenue * (projected_margin / 100)
        depreciation = projected_revenue * (growth.depreciation_pct / 100)
        capex = projected_revenue * (growth.capex_pct / 100)
        working_capital = max(
            (projected_revenue - previous_revenue) * (growth.working_capital_pct / 100), 0
        )

        # Rounded here, as the source does, so rounding is part of the
        # valuation rather than a display concern.
        rows.append(
            ProjectionYear(
                label=year + i,
                ebit=js_round(projected_ebitda - depreciation),
                depreciation=js_round(depreciation),
                capex=js_round(capex),
                working_capital=js_round(working_capital),
            )
        )
        previous_revenue = projected_revenue

    return tuple(rows)


def _current_year() -> int:
    from datetime import UTC, datetime

    return datetime.now(UTC).year


def wacc(
    *,
    cost_of_equity: float,
    cost_of_debt: float,
    size_premium_pct: float,
    equity_value: float,
    debt: float,
    tax_rate_pct: float,
) -> float:
    """Weighted average cost of capital, as a decimal.

    `tax_rate_pct` of 0 stays 0 — the source's `tax || 20` turned a genuine
    0% jurisdiction into 20%.
    """
    equity = equity_value or 1
    total = equity + debt
    after_tax_debt = (cost_of_debt / 100) * (1 - tax_rate_pct / 100)
    return (
        (equity / total) * (cost_of_equity / 100)
        + (debt / total) * after_tax_debt
        + size_premium_pct / 100
    )


def discounted_cash_flow(inputs: ValuationInputs) -> DcfResult:
    """Free cash flow to the firm, discounted at WACC, with a Gordon growth
    terminal value."""
    growth = growth_benchmark(inputs.sector)
    benchmark = wacc_benchmark(inputs.sector)
    cost_of_equity = round(benchmark[0], 2) if benchmark else _DEFAULT_COST_OF_EQUITY
    cost_of_debt = round(benchmark[1], 2) if benchmark else _DEFAULT_COST_OF_DEBT
    tax_pct = tax_rate(inputs.geography)

    projection = project(inputs)
    rate = wacc(
        cost_of_equity=cost_of_equity,
        cost_of_debt=cost_of_debt,
        size_premium_pct=size_premium(inputs.revenue or 0),
        equity_value=max((inputs.revenue or 0) * 3, 1_000_000),
        debt=inputs.debt,
        tax_rate_pct=tax_pct,
    )

    terminal_growth = (growth.terminal_growth or 2) / 100
    sum_discounted = 0.0
    free_cash_flows: list[float] = []

    for i, row in enumerate(projection):
        nopat = row.ebit * (1 - tax_pct / 100)
        fcf = nopat + row.depreciation - row.capex - row.working_capital
        sum_discounted += fcf / (1 + rate) ** (i + 1)
        free_cash_flows.append(fcf)

    final_fcf = free_cash_flows[-1] if free_cash_flows else 0.0
    # A tiny floor on the denominator keeps a terminal growth rate at or
    # above WACC from producing an infinite or negative value.
    denominator = max(rate - terminal_growth, 0.001)
    raw_terminal = final_fcf * (1 + terminal_growth) / denominator / (1 + rate) ** len(projection)
    floored = final_fcf < 0
    terminal_value = 0.0 if floored else raw_terminal

    enterprise_value = max(sum_discounted + terminal_value, 0)
    equity_before_dlom = max(enterprise_value + inputs.cash - inputs.debt, 0)

    return DcfResult(
        enterprise_value=enterprise_value,
        equity_value=equity_before_dlom * (1 - inputs.dlom_pct / 100),
        wacc=rate,
        terminal_value=terminal_value,
        terminal_value_floored=floored,
        sum_discounted_fcf=sum_discounted,
        projection=projection,
    )


def _size_discount_pct(comps: tuple[ListedComp, ...], target_revenue: float) -> float:
    """Listed comparables are typically orders of magnitude larger than an
    SME, and a $3m business does not trade at a mega-cap's multiple. The
    discount scales with how far below the peer set the target sits.
    """
    revenues = sorted(c.rev for c in comps if c.rev and c.rev > 0)
    target_millions = target_revenue / 1e6
    if not revenues or target_millions <= 0:
        return 0.0

    # Upper median, as everywhere else in this port.
    median_comp = revenues[len(revenues) // 2]
    ratio = median_comp / target_millions
    if ratio >= 1000:
        return 40.0
    if ratio >= 250:
        return 30.0
    if ratio >= 50:
        return 20.0
    if ratio >= 10:
        return 10.0
    return 0.0


def trading_comps(
    inputs: ValuationInputs, comps: tuple[ListedComp, ...]
) -> tuple[MultipleRange, MultipleRange]:
    """`(EV/Revenue, EV/EBITDA)` multiple ranges from listed comparables.

    The haircut and the size discount compose multiplicatively here, and the
    range is built off the **median** multiple.
    """
    valid = tuple(c for c in comps if c.rev and c.rev > 0)
    revenue_multiples = [c.ev / c.rev for c in valid if c.ev and c.rev]
    ebitda_multiples = [c.ev / c.ebitda for c in valid if c.ev and c.ebitda and c.ebitda > 0]

    negative_ebitda = inputs.adjusted_ebitda < 0
    size_discount = _size_discount_pct(comps, inputs.revenue or 0)

    def build(multiples: list[float], haircut_pct: float) -> MultipleRange:
        base = (
            min(haircut_pct + _NEGATIVE_EBITDA_SURCHARGE_PCT, 100)
            if negative_ebitda
            else haircut_pct
        )
        keep = (1 - base / 100) * (1 - size_discount / 100)
        s = stats(multiples)
        return MultipleRange(
            low=s.p25 * keep,
            mid=s.median * keep,
            high=s.p75 * keep,
            stats=s,
            applied_discount_pct=js_round((1 - keep) * 100),
        )

    return (
        build(revenue_multiples, inputs.haircut_revenue_pct),
        build(ebitda_multiples, inputs.haircut_ebitda_pct),
    )


def transaction_comps(inputs: ValuationInputs) -> tuple[MultipleRange, MultipleRange]:
    """`(EV/Revenue, EV/EBITDA)` from matched M&A transactions.

    Unlike trading comps this uses the **mean** multiple for the mid, and the
    haircut is additive with the negative-EBITDA surcharge — there is no size
    discount, because private deal comparables are already SME-scale.
    """
    deals = match_transactions(inputs.sector)
    revenue_multiples = [d.ev_revenue for d in deals if d.ev_revenue and d.ev_revenue > 0]
    ebitda_multiples = [d.ev_ebitda for d in deals if d.ev_ebitda and d.ev_ebitda > 0]
    negative_ebitda = inputs.adjusted_ebitda < 0

    def build(multiples: list[float], haircut_pct: float) -> MultipleRange:
        applied = (
            min(haircut_pct + _NEGATIVE_EBITDA_SURCHARGE_PCT, 100)
            if negative_ebitda
            else haircut_pct
        )
        keep = 1 - applied / 100
        s = stats(multiples)
        return MultipleRange(
            low=s.p25 * keep,
            mid=s.avg * keep,
            high=s.p75 * keep,
            stats=s,
            applied_discount_pct=applied,
        )

    return (
        build(revenue_multiples, inputs.haircut_revenue_pct),
        build(ebitda_multiples, inputs.haircut_ebitda_pct),
    )


def industry_research(inputs: ValuationInputs, *, discount_pct: float = 0.0) -> MultipleRange:
    """Revenue multiples from matched venture rounds.

    The mid blends the current-year and forward multiples; the range comes
    from the quartiles of both pooled together.
    """
    rounds = match_vc_rounds(inputs.sector, inputs.stage)
    current = [r.fy_multiple for r in rounds if r.fy_multiple is not None]
    forward = [r.forward_multiple for r in rounds if r.forward_multiple is not None]

    avg_current = sum(current) / len(current) if current else 0.0
    avg_forward = sum(forward) / len(forward) if forward else 0.0
    blended = (avg_current + avg_forward) / 2 or avg_current or avg_forward

    pooled = [m for m in [*current, *forward] if m]
    s = stats(pooled)
    keep = 1 - discount_pct / 100
    return MultipleRange(
        low=s.p25 * keep,
        mid=blended * keep,
        high=s.p75 * keep,
        stats=s,
        applied_discount_pct=discount_pct,
    )


def _clamped(name: str, low: float, mid: float, high: float) -> MethodRow:
    """Sorts the three values, so a low above a mid cannot survive into the
    report."""
    ordered = sorted((low, mid, high))
    return MethodRow(name=name, low=ordered[0], mid=ordered[1], high=ordered[2])


def value_company(inputs: ValuationInputs) -> Valuation:
    """The blended valuation: an unweighted mean across whichever methods
    produced a positive mid.

    This is the whole deterministic fallback. Note what is *not* included: a
    transaction EV/EBITDA row. The source computes those multiples but never
    adds them to the blend, and reproducing the blend faithfully matters more
    than tidying that.
    """
    revenue = inputs.revenue or 0
    ebitda = inputs.adjusted_ebitda
    comps = inputs.ai_comps or _static_comps_for(inputs.sector)

    dcf = discounted_cash_flow(inputs) if revenue > 0 else None
    trading_revenue, trading_ebitda = trading_comps(inputs, comps)
    transaction_revenue, _ = transaction_comps(inputs)
    industry = industry_research(inputs)

    rows: list[MethodRow] = []
    if dcf and dcf.equity_value > 0:
        rows.append(
            _clamped(
                "DCF Analysis", dcf.equity_value * 0.75, dcf.equity_value, dcf.equity_value * 1.25
            )
        )
    if trading_revenue.mid > 0 and revenue > 0:
        rows.append(
            _clamped(
                "Trading Comps (EV/Revenue)",
                trading_revenue.low * revenue,
                trading_revenue.mid * revenue,
                trading_revenue.high * revenue,
            )
        )
    if ebitda > 0 and trading_ebitda.mid > 0:
        rows.append(
            _clamped(
                "Trading Comps (EV/EBITDA)",
                trading_ebitda.low * ebitda,
                trading_ebitda.mid * ebitda,
                trading_ebitda.high * ebitda,
            )
        )
    if transaction_revenue.mid > 0 and revenue > 0:
        rows.append(
            _clamped(
                "Transaction Comps (EV/Revenue)",
                transaction_revenue.low * revenue,
                transaction_revenue.mid * revenue,
                transaction_revenue.high * revenue,
            )
        )
    if industry.mid > 0 and revenue > 0:
        rows.append(
            _clamped(
                "Industry Research (VC Rounds)",
                industry.low * revenue,
                industry.mid * revenue,
                industry.high * revenue,
            )
        )

    if not rows:
        return Valuation(low=0, mid=0, high=0, methods=(), dcf=dcf)

    def mean(values: list[float]) -> float:
        return sum(values) / len(values)

    ordered = sorted(
        (
            mean([r.low for r in rows]),
            mean([r.mid for r in rows]),
            mean([r.high for r in rows]),
        )
    )
    return Valuation(low=ordered[0], mid=ordered[1], high=ordered[2], methods=tuple(rows), dcf=dcf)


def _static_comps_for(sector: str | None) -> tuple[ListedComp, ...]:
    from app.modules.lead_magnets.domain.valuation import comps_for_sector

    return comps_for_sector(sector)
