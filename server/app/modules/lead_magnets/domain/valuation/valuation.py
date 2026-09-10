"""Sector resolution, peer matching and the statistics the valuation methods
are built on. Pure.

Ported from `dopamine-valuation.html`. Several details here look arbitrary
and are not — each is called out where it would otherwise be "tidied" into a
different number:

- `peer_median_margin` takes the **upper** median of an even-length set
  (`m[len // 2]`), not the mean of the middle two. `statistics.median` would
  return a different figure and shift every trading-comps valuation.
- `stats` interpolates percentiles at `q * (n - 1)`, which is NumPy's
  `linear` method and not the only convention.
- Peer matching scores the first search term higher than the rest, and both
  sorts are stable, so equal-scoring rows keep dataset order. Python's
  `sorted` and modern JavaScript's `Array.sort` agree on that.

One deliberate divergence from the source, in `tax_rate` — see its
docstring. Everything else was checked by equivalence against the original
JavaScript over 350 cases.
"""

import math
import re
from dataclasses import dataclass

from app.modules.lead_magnets.domain.valuation.valuation_data import (
    GrowthBenchmark,
    ListedComp,
    Transaction,
    VcRound,
    damodaran_wacc,
    industry_growth,
    sector_aliases,
    sector_to_comps_key,
    sector_to_damodaran,
    static_comps,
    transactions,
    vc_rounds,
)

# Corporate tax rate by geography, in percent. Anything unlisted falls back
# to 20, matching the source.
_TAX_RATES: dict[str, float] = {
    "United Arab Emirates": 9,
    "UAE": 9,
    "Saudi Arabia": 20,
    "KSA": 20,
    "Egypt": 22.5,
    "United Kingdom": 25,
    "UK": 25,
    "France": 25,
    "Germany": 30,
    "United States": 21,
    "USA": 21,
    "United States of America": 21,
    "Singapore": 17,
    "India": 25,
    "Pakistan": 29,
    "Nigeria": 30,
    "South Africa": 27,
    "Kenya": 30,
    "Turkey": 23,
    "Qatar": 0,
    "Bahrain": 0,
    "Kuwait": 15,
    "Jordan": 20,
    "Lebanon": 17,
    "Morocco": 31,
    "Tunisia": 25,
}
_DEFAULT_TAX_RATE = 20.0

# Used when a sector matches no growth benchmark at all.
_DEFAULT_GROWTH = GrowthBenchmark(
    revenue_growth=20,
    ebit_margin_improvement=3,
    depreciation_pct=5,
    capex_pct=8,
    working_capital_pct=4,
    terminal_growth=2.0,
)

_WORD_SPLIT = re.compile(r"[\s&,]+")


@dataclass(frozen=True)
class Stats:
    min: float
    p25: float
    avg: float
    median: float
    p75: float
    max: float


def resolve_sector(sector: str | None) -> str | None:
    """The tool's own sector vocabulary is wider than the datasets'; aliases
    map the long tail onto a key that has data behind it."""
    if sector is None:
        return None
    return sector_aliases().get(sector, sector)


def tax_rate(geography: str | None) -> float:
    """Corporate tax rate in percent, defaulting to 20 for anything unlisted.

    **Deliberately not bug-for-bug faithful.** The source reads
    `return t[geo] || 20`, and JavaScript treats `0` as falsy — so Qatar and
    Bahrain, whose table entries are correctly `0`, are silently taxed at 20%
    instead. That inflates the tax drag in the DCF and undervalues every
    Qatari and Bahraini business, two core GCC markets for this firm.

    This returns the table's 0. The divergence is intentional and tested;
    reproducing the bug would mean knowingly under-valuing real companies.
    """
    return _TAX_RATES.get(geography or "", _DEFAULT_TAX_RATE)


def stats(values: list[float]) -> Stats:
    """Min, quartiles, mean, median and max.

    An empty set returns zeroes rather than `None`, matching the source —
    the callers treat a zero multiple as "this method contributed nothing".
    """
    if not values:
        return Stats(0, 0, 0, 0, 0, 0)

    ordered = sorted(values)
    n = len(ordered)

    def percentile(q: float) -> float:
        i = q * (n - 1)
        lo, hi = math.floor(i), math.ceil(i)
        if lo == hi:
            return ordered[lo]
        return ordered[lo] * (hi - i) + ordered[hi] * (i - lo)

    return Stats(
        min=ordered[0],
        p25=percentile(0.25),
        avg=sum(ordered) / n,
        median=percentile(0.5),
        p75=percentile(0.75),
        max=ordered[n - 1],
    )


def comps_for_sector(sector: str | None) -> tuple[ListedComp, ...]:
    """The static listed comparables for a sector, through the alias and
    comps-key mappings in the same order the source tries them.

    This is the shortfall fallback: what fills the gap when grounded search
    returns fewer comparables than the tool asks for, instead of letting a
    model invent figures.
    """
    table = static_comps()
    resolved = resolve_sector(sector)
    keys = (
        sector,
        resolved,
        sector_to_comps_key().get(sector or ""),
        sector_to_comps_key().get(resolved or ""),
    )
    for key in keys:
        if key and key in table:
            return table[key]
    return ()


def trading_comps_for_sector(sector: str | None) -> tuple[ListedComp, ...]:
    """The comparable set the trading-comps method uses.

    Deliberately a different function from `comps_for_sector`, not a wider
    version of it. `TradingComps` in the source has a fuzzy tier that
    `getPeerMedianMargin` does not — it word-matches the sector against the
    comp-set keys — and folding that into one function would change the peer
    margin, which is verified against the source over 350 cases.

    **One tier of the source is deliberately not ported.** When nothing
    matches at all, it falls back to Microsoft, Alphabet and Apple. Valuing
    an unmatched UAE fit-out contractor against mega-cap tech is worse than
    returning nothing: the report would show a comparables table that is
    visibly absurd, and "no comparable set found" is the honest answer. The
    caller decides what to say instead.
    """
    exact = comps_for_sector(sector)
    if exact:
        return exact

    table = static_comps()
    words = [w for w in _WORD_SPLIT.split((sector or "").lower()) if len(w) > 2]
    for key in table:
        if any(word in key.lower() for word in words):
            return table[key]
    return ()


def peer_median_margin(
    sector: str | None, ai_comps: list[ListedComp] | None = None
) -> float | None:
    """Median EBITDA margin of the peer set, in percent.

    Prefers the model's own comparables when it produced any, falling back to
    the static set. Only peers with positive revenue *and* positive EBITDA
    count — a loss-making peer would drag the margin below what any buyer
    would underwrite.

    Takes the upper median of an even-length set, as the source does.
    """
    peers: tuple[ListedComp, ...] | list[ListedComp] = ai_comps or comps_for_sector(sector)
    margins = sorted(
        c.ebitda / c.rev * 100
        for c in peers
        if c and c.rev and c.rev > 0 and c.ebitda and c.ebitda > 0
    )
    if not margins:
        return None
    return margins[len(margins) // 2]


def growth_benchmark(sector: str | None) -> GrowthBenchmark:
    """Auto-DCF assumptions for a sector: exact match, then alias, then a
    substring match in either direction, then a generic default."""
    if not sector:
        return _DEFAULT_GROWTH

    table = industry_growth()
    if sector in table:
        return table[sector]

    alias = sector_aliases().get(sector)
    if alias and alias in table:
        return table[alias]

    lowered = sector.lower()
    for key, value in table.items():
        if lowered in key.lower() or key.lower() in lowered:
            return value
    return _DEFAULT_GROWTH


def wacc_benchmark(sector: str | None) -> tuple[float, float, str] | None:
    """`(cost of equity, cost of debt, industry)` in percent, or `None`.

    Falls back to the whole-market figures rather than nothing, because a
    DCF with no discount rate is not a valuation.
    """
    if not sector:
        return None

    table = damodaran_wacc()
    mapping = sector_to_damodaran()
    key = mapping.get(sector) or mapping.get(sector_aliases().get(sector, ""))
    if key and key in table:
        ke, kd = table[key]
        return ke, kd, key

    lowered = sector.lower()
    for sector_name, industry in mapping.items():
        if lowered in sector_name.lower() or sector_name.lower() in lowered:
            if industry in table:
                ke, kd = table[industry]
                return ke, kd, industry

    if "Total Market" in table:
        ke, kd = table["Total Market"]
        return ke, kd, "Total Market (fallback)"
    return None


def _score_terms(sector: str | None, override_terms: list[str] | None) -> list[str]:
    terms = override_terms or [sector, resolve_sector(sector)]
    return [str(t).lower() for t in terms if t]


def match_transactions(
    sector: str | None, *, limit: int = 15, override_terms: list[str] | None = None
) -> list[Transaction]:
    """M&A comparables, best match first.

    The first term scores 3 and later ones 2, so the analyst's own preferred
    term outranks the auto-assigned tag when one is supplied; individual
    words longer than two characters add 1 each. Only positive scores
    qualify.
    """
    terms = _score_terms(sector, override_terms)
    scored: list[tuple[int, int, Transaction]] = []

    for index, row in enumerate(transactions()):
        verticals = (row.verticals or "").lower()
        score = 0
        for position, term in enumerate(terms):
            if term in verticals:
                score += 3 if position == 0 else 2
            for word in _WORD_SPLIT.split(term):
                if len(word) > 2 and word in verticals:
                    score += 1
        if score > 0:
            scored.append((score, index, row))

    # Stable, so equal scores keep dataset order — as in the source.
    scored.sort(key=lambda item: -item[0])
    return [row for _, _, row in scored[:limit]]


def match_vc_rounds(
    sector: str | None, stage: str | None = None, *, override_terms: list[str] | None = None
) -> list[VcRound]:
    """Venture rounds, best match first.

    Sector matching here is **exact**, not a substring: the VC dataset's
    sector labels are short and a substring match pulls in unrelated rounds.
    A matching stage adds 2.
    """
    terms = _score_terms(sector, override_terms)
    scored: list[tuple[int, int, VcRound]] = []

    for index, row in enumerate(vc_rounds()):
        row_sector = (row.sector or "").lower()
        score = 0
        for position, term in enumerate(terms):
            if row_sector == term:
                score += 3 if position == 0 else 2
            for word in _WORD_SPLIT.split(term):
                if len(word) > 2 and word in row_sector:
                    score += 1
        if row.stage and stage and row.stage.lower() == stage.lower():
            score += 2
        if score > 0:
            scored.append((score, index, row))

    scored.sort(key=lambda item: -item[0])
    return [row for _, _, row in scored]
