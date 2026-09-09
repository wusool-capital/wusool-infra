"""The GCC SME Benchmark scoring engine. Pure, and the whole of the tool's
output — no model is involved in what the visitor sees.

That makes this the one lead magnet with no AI dependency at all, and the
reason it is the safest to cut over first.

Everything computes in USD. The live tool offers an AED/USD toggle, but it
governs data entry and display only: `toCalc` divides AED input by the peg on
the way in, and the value that reaches Attio goes through a round-only
`toUSD`. The `_aed` suffix on the benchmark list's Attio attributes is a
misnomer — those fields hold USD, and the live code even names a local
`rentAed` while assigning a USD figure to it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

ANCHOR_PERCENTILES = (10, 25, 50, 75, 90)

Mode = Literal["sme", "tech"]

# Metric key -> the `seller_roles` percentile column it lands in. Seven SME
# metrics plus the two tech-only ones account for all nine `pct_*` columns.
PERCENTILE_COLUMNS: dict[str, str] = {
    "ebitda": "pct_ebitda_margin",
    "growth": "pct_revenue_growth",
    "revEmp": "pct_revenue_per_employee",
    "conc": "pct_concentration",
    "gm": "pct_gross_margin",
    "rent": "pct_premises_cost",
    "recur": "pct_recurring_revenue",
    "capEff": "pct_capital_efficiency",
    "revScale": "pct_revenue_scale",
}

QUARTILE_LABELS = ("", "Bottom 25%", "Below Average", "Above Average", "Top 25%")


@dataclass(frozen=True)
class MetricSpec:
    label: str
    unit: str
    higher_is_better: bool
    weight: int


@dataclass(frozen=True)
class Band:
    """A revenue peer band. The multipliers shift the sector anchors so a
    micro business is not scored against mid-market operating leverage."""

    id: str
    label: str
    max_usd: float | None
    ebitda_adj: float
    rev_emp_mult: float
    rent_mult: float


@dataclass(frozen=True)
class PeerCut:
    """One sector (SME mode) or funding stage (startup mode) — the peer set a
    submission is ranked against. Startup mode cuts by stage rather than
    sector because sector cuts in the source sample run n=3 to 6."""

    label: str
    sample_size: int | None
    anchors: Mapping[str, Sequence[float]]
    multi_site: bool = False
    b2b: bool = False


@dataclass(frozen=True)
class MetricResult:
    key: str
    value: float | None
    percentile: float | None
    quartile: int | None
    anchors: tuple[float, ...] | None
    spec: MetricSpec


def percentile_rank(value: float | None, anchors: Sequence[float]) -> float | None:
    """Piecewise-linear rank against the five anchors, with linear
    extrapolation into both tails.

    Ported exactly, including the details that look arbitrary and are not:
    the tails extrapolate at 15 percentile points per anchor step and clamp
    at 1 and 99, so no submission is ever reported as a 0th or 100th
    percentile of a modelled distribution. A zero-width anchor step falls
    back to 1 to avoid dividing by zero on a flat sector.
    """
    if value is None or not anchors:
        return None

    if value <= anchors[0]:
        step = (anchors[1] - anchors[0]) or 1
        return max(1.0, 10 - ((anchors[0] - value) / step) * 15)

    if value >= anchors[4]:
        step = (anchors[4] - anchors[3]) or 1
        return min(99.0, 90 + ((value - anchors[4]) / step) * 15)

    for i in range(4):
        if anchors[i] <= value <= anchors[i + 1]:
            span = (anchors[i + 1] - anchors[i]) or 1
            low, high = ANCHOR_PERCENTILES[i], ANCHOR_PERCENTILES[i + 1]
            return low + ((value - anchors[i]) / span) * (high - low)

    return 50.0


def band_for(revenue_usd: float | None, bands: Sequence[Band]) -> Band:
    """The first band whose ceiling the revenue is under; the open-ended top
    band otherwise. A missing revenue lands in the lowest band, matching the
    live `bandFor` — `null < 545000` is true in JavaScript.
    """
    for band in bands:
        if band.max_usd is None or (revenue_usd or 0) < band.max_usd:
            return band
    return bands[-1]


def adjusted_anchors(
    key: str, anchors: Sequence[float], band: Band, *, mode: Mode
) -> tuple[float, ...]:
    """Shifts a sector's anchors for the submission's revenue band.

    Startup mode returns them untouched: the funding stage *is* the cut
    there, so applying a revenue band on top would double-count size.
    """
    if mode != "sme":
        return tuple(anchors)
    if key == "ebitda":
        return tuple(a + band.ebitda_adj for a in anchors)
    if key == "revEmp":
        return tuple(a * band.rev_emp_mult for a in anchors)
    if key == "rent":
        return tuple(a * (band.rent_mult or 1) for a in anchors)
    return tuple(anchors)


def quartile(percentile: float) -> int:
    return 1 if percentile < 25 else 2 if percentile < 50 else 3 if percentile < 75 else 4


def score_metrics(
    values: Mapping[str, float | None],
    *,
    specs: Mapping[str, MetricSpec],
    cut: PeerCut,
    band: Band,
    mode: Mode,
) -> tuple[dict[str, MetricResult], float, float]:
    """Ranks every metric the peer cut has anchors for.

    Returns `(results, score, weight_covered)`. `weight_covered` is the live
    tool's `dataCompleteness` — the summed weight of the metrics that could
    actually be ranked, which is how a half-filled form is distinguished from
    a genuinely average one.

    A `higher_is_better=False` metric is inverted *before* clamping, so
    concentration and premises cost read the same direction as everything
    else.
    """
    results: dict[str, MetricResult] = {}
    weight_sum = 0.0
    weighted_percentile = 0.0

    for key, spec in specs.items():
        value = values.get(key)
        anchors = cut.anchors.get(key)
        if value is None or not anchors:
            results[key] = MetricResult(key, value, None, None, None, spec)
            continue

        adjusted = adjusted_anchors(key, anchors, band, mode=mode)
        percentile = percentile_rank(value, adjusted)
        assert percentile is not None
        if not spec.higher_is_better:
            percentile = 100 - percentile
        percentile = max(1.0, min(99.0, percentile))

        results[key] = MetricResult(key, value, percentile, quartile(percentile), adjusted, spec)
        weight_sum += spec.weight
        weighted_percentile += percentile * spec.weight

    score = round(weighted_percentile / weight_sum) if weight_sum else 50.0
    return results, score, weight_sum
