"""One benchmark submission, end to end: raw form figures in, the full
result out. Pure — this is the whole of what the visitor sees, and no model
is involved in any of it.

Every money field is USD. The live tool's AED/USD toggle converts on entry,
so by the time a figure reaches here the conversion has already happened —
see `benchmark.py` on why the `_aed` Attio slugs nonetheless hold USD.
"""

from dataclasses import dataclass

from app.modules.lead_magnets.domain.benchmark.benchmark import (
    Band,
    MetricResult,
    MetricSpec,
    Mode,
    PeerCut,
    band_for,
    score_metrics,
)
from app.modules.lead_magnets.domain.benchmark.benchmark_dataset import (
    BANDS,
    SECTORS,
    SME_METRICS,
    STAGES,
    TECH_METRICS,
)
from app.modules.lead_magnets.domain.benchmark.benchmark_narrative import Flag, flag_for
from app.modules.lead_magnets.domain.benchmark.benchmark_routing import (
    Quality,
    Routing,
    headline_flag,
    quality,
    route,
    score_band,
)


@dataclass(frozen=True)
class BenchmarkInputs:
    """What the form collects, already in USD.

    `salary_deducted` is the one input that changes the meaning of another:
    when the owner's salary is already deducted from reported operating
    profit, it is added back so the figure is comparable with a peer set
    whose owners pay themselves differently.
    """

    mode: Mode
    peer_key: str
    revenue: float | None = None
    prev_revenue: float | None = None
    ebitda_reported: float | None = None
    owner_salary: float | None = None
    salary_deducted: bool = False
    gross_margin_pct: float | None = None
    headcount: int | None = None
    rent_cost: float | None = None
    capital_raised: float | None = None
    top_customer_pct: float | None = None
    recurring_pct: float | None = None
    years_active: float | None = None
    outlets: int | None = None
    days_to_get_paid: int | None = None
    email: str | None = None
    geography: str | None = None


@dataclass(frozen=True)
class ImpliedEnterpriseValue:
    low: float
    mid: float
    high: float
    forward_revenue: float
    multiples: tuple[float, float, float]


@dataclass(frozen=True)
class BenchmarkResult:
    score: int
    band: str
    quartile: int
    peer_label: str
    revenue_band: Band
    sample_size: int | None
    metrics: dict[str, MetricResult]
    percentiles: dict[str, float | None]
    flags: list[Flag]
    routing: Routing
    quality: Quality
    headline: str
    ebitda_adjusted: float | None
    data_completeness: int
    metrics_covered: int
    metrics_total: int
    implied_ev: ImpliedEnterpriseValue | None


def adjusted_ebitda(inputs: BenchmarkInputs) -> float | None:
    """Reported operating profit with the owner's salary added back, when the
    visitor said it had been deducted."""
    if inputs.ebitda_reported is None:
        return None
    salary = (inputs.owner_salary or 0) if inputs.salary_deducted else 0
    return inputs.ebitda_reported + salary


def metric_values(inputs: BenchmarkInputs) -> dict[str, float | None]:
    """The ratios the peer set is ranked on, derived from the raw figures.

    A ratio whose denominator is missing or zero is `None`, never zero — a
    blank field must drop out of the score rather than rank at the bottom of
    it.
    """
    tech = inputs.mode == "tech"
    revenue = inputs.revenue
    prev = inputs.prev_revenue
    adj = adjusted_ebitda(inputs)

    return {
        "ebitda": (adj / revenue) * 100 if revenue and adj is not None else None,
        "gm": inputs.gross_margin_pct,
        "growth": ((revenue - prev) / prev) * 100 if revenue and prev and prev > 0 else None,
        # Thousands, matching the dataset's own units.
        "revEmp": (revenue / inputs.headcount) / 1000 if revenue and inputs.headcount else None,
        "rent": (inputs.rent_cost / revenue) * 100
        if not tech and inputs.rent_cost is not None and revenue
        else None,
        "conc": inputs.top_customer_pct,
        "recur": inputs.recurring_pct,
        "revScale": revenue if tech else None,
        "capEff": revenue / inputs.capital_raised
        if tech and revenue and inputs.capital_raised and inputs.capital_raised > 0
        else None,
    }


def implied_enterprise_value(
    inputs: BenchmarkInputs, cut: PeerCut
) -> ImpliedEnterpriseValue | None:
    """Startup mode only: enterprise value from observed forward revenue
    multiples.

    Next-year revenue is projected by repeating the current growth rate, and
    falls back to 1.5x when the company is flat or shrinking — without that
    floor a declining company would project a *lower* forward revenue than
    it has today and price below its own trailing figure.
    """
    forward_multiples = cut.anchors.get("fwdMult")
    if inputs.mode != "tech" or not forward_multiples or not inputs.revenue:
        return None

    revenue, prev = inputs.revenue, inputs.prev_revenue
    forward = revenue * (revenue / prev) if prev and prev > 0 and revenue > prev else revenue * 1.5
    low, mid, high = forward_multiples[1], forward_multiples[2], forward_multiples[3]
    return ImpliedEnterpriseValue(
        low=forward * low,
        mid=forward * mid,
        high=forward * high,
        forward_revenue=forward,
        multiples=(low, mid, high),
    )


def evaluate(inputs: BenchmarkInputs) -> BenchmarkResult:
    """Score, rank, narrate and triage one submission."""
    tech = inputs.mode == "tech"
    cuts: dict[str, PeerCut] = STAGES if tech else SECTORS
    specs: dict[str, MetricSpec] = TECH_METRICS if tech else SME_METRICS

    cut = cuts[inputs.peer_key]
    # In startup mode the funding stage is the peer cut, so no revenue band
    # is applied; a band is still resolved for reporting.
    band = band_for(inputs.revenue, BANDS)

    values = metric_values(inputs)
    metrics, score, weight_covered = score_metrics(
        values, specs=specs, cut=cut, band=band, mode=inputs.mode
    )
    percentiles = {key: result.percentile for key, result in metrics.items()}

    flags = [
        flag
        for result in metrics.values()
        if (flag := flag_for(result, peer_label=cut.label, mode=inputs.mode)) is not None
    ]
    flags.sort(key=lambda f: f.percentile)

    overall_quartile = 1 if score < 25 else 2 if score < 50 else 3 if score < 75 else 4

    return BenchmarkResult(
        score=score,
        band=score_band(score),
        quartile=overall_quartile,
        peer_label=cut.label,
        revenue_band=band,
        sample_size=cut.sample_size,
        metrics=metrics,
        percentiles=percentiles,
        flags=flags,
        routing=route(
            mode=inputs.mode,
            revenue_usd=inputs.revenue,
            years_active=inputs.years_active,
            data_completeness=weight_covered,
            percentiles=percentiles,
        ),
        quality=quality(
            mode=inputs.mode,
            email=inputs.email,
            revenue_usd=inputs.revenue,
            headcount=inputs.headcount,
            gross_margin_pct=inputs.gross_margin_pct,
            ebitda_adjusted_usd=adjusted_ebitda(inputs),
            prev_revenue_usd=inputs.prev_revenue,
        ),
        headline=headline_flag(percentiles),
        ebitda_adjusted=adjusted_ebitda(inputs),
        data_completeness=weight_covered,
        metrics_covered=sum(1 for p in percentiles.values() if p is not None),
        metrics_total=len(specs),
        implied_ev=implied_enterprise_value(inputs, cut),
    )
