"""The valuation tool's reference datasets, loaded from
`data/valuation.json`.

A data file rather than generated Python: it is 1,000 M&A transactions, 127
VC rounds and 31 sectors of listed comparables, which reads and diffs far
better as JSON than as a quarter-megabyte of source. Extracted verbatim from
the `MA_RAW`, `VC_RAW`, `PUBLIC_COMPS`, `SECTOR_ALIASES`, `DAMODARAN_WACC`,
`SECTOR_TO_DAMODARAN`, `SECTOR_TO_COMPS_KEY` and `INDUSTRY_GROWTH` blocks in
`dopamine-valuation.html`.

Field names are expanded from the single letters the source uses (`t`, `v`,
`h`, `d`, `e`, `r`, `b`) — those are wire-format economy in a 566KB page, not
meaning. The mapping was read off the tool's own render code
(`{ev: r.e, evRev: r.r, evEb: r.b}`), not guessed.

`static_comps` is the shortfall fallback: when grounded search returns fewer
comparables than the tool asks for, these are what fill the gap rather than
letting a model invent figures. Its records are already the
`{co, tk, ev, rev, ebitda}` shape the page parses.

Read once and cached. Loading a packaged data file at import is the same
mechanism `api/static.py` uses for the tool pages, and works from the wheel.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.modules.utilities.domain.json_types import JsonObject

_DATA = Path(__file__).resolve().parent / "data" / "valuation.json"


@dataclass(frozen=True)
class Transaction:
    """One M&A comparable. Multiples are as reported; `ev` is in millions."""

    target: str
    verticals: str
    hq: str | None
    date: str | None
    ev: float | None
    ev_revenue: float | None
    ev_ebitda: float | None
    theme: str | None


@dataclass(frozen=True)
class VcRound:
    """One venture round. `fy_multiple` is the current-year revenue multiple,
    `forward_multiple` the forward one; the Industry Research method blends
    the two."""

    company: str
    sector: str | None
    stage: str | None
    hq: str | None
    revenue_prior: float | None
    revenue_current: float | None
    valuation: float | None
    raised: float | None
    fy_multiple: float | None
    forward_multiple: float | None


@dataclass(frozen=True)
class ListedComp:
    """A listed comparable. Field names are the page's own — `/compare`
    returns this shape verbatim."""

    co: str
    tk: str
    ev: float | None
    rev: float | None
    ebitda: float | None


@dataclass(frozen=True)
class WaccBenchmark:
    """Damodaran cost of equity and after-tax cost of debt, in percent."""

    cost_of_equity: float
    cost_of_debt: float
    industry: str


@dataclass(frozen=True)
class GrowthBenchmark:
    """Auto-DCF assumptions for a sector, all in percent."""

    revenue_growth: float
    ebit_margin_improvement: float
    depreciation_pct: float
    capex_pct: float
    working_capital_pct: float
    terminal_growth: float


@lru_cache
def _raw() -> JsonObject:
    return json.loads(_DATA.read_text(encoding="utf-8"))


@lru_cache
def transactions() -> tuple[Transaction, ...]:
    return tuple(
        Transaction(
            target=r.get("t", ""),
            verticals=r.get("v") or "",
            hq=r.get("h"),
            date=r.get("d"),
            ev=r.get("e"),
            ev_revenue=r.get("r"),
            ev_ebitda=r.get("b"),
            theme=r.get("th"),
        )
        for r in _raw()["transactions"]
    )


@lru_cache
def vc_rounds() -> tuple[VcRound, ...]:
    return tuple(
        VcRound(
            company=r.get("c", ""),
            sector=r.get("s"),
            stage=r.get("st"),
            hq=r.get("h"),
            revenue_prior=r.get("r24"),
            revenue_current=r.get("r25"),
            valuation=r.get("v"),
            raised=r.get("rs"),
            fy_multiple=r.get("fm"),
            forward_multiple=r.get("fw"),
        )
        for r in _raw()["vc_rounds"]
    )


@lru_cache
def static_comps() -> dict[str, tuple[ListedComp, ...]]:
    return {
        sector: tuple(
            ListedComp(
                co=c.get("co", ""),
                tk=c.get("tk", ""),
                ev=c.get("ev"),
                rev=c.get("rev"),
                ebitda=c.get("ebitda"),
            )
            for c in comps
        )
        for sector, comps in _raw()["static_comps"].items()
    }


@lru_cache
def sector_aliases() -> dict[str, str]:
    return dict(_raw()["sector_aliases"])


@lru_cache
def sector_to_damodaran() -> dict[str, str]:
    return dict(_raw()["sector_to_damodaran"])


@lru_cache
def sector_to_comps_key() -> dict[str, str]:
    return dict(_raw()["sector_to_comps_key"])


@lru_cache
def damodaran_wacc() -> dict[str, tuple[float, float]]:
    """`industry -> (cost of equity, cost of debt)`."""
    return {k: (v["ke"], v["kd"]) for k, v in _raw()["damodaran_wacc"].items()}


@lru_cache
def industry_growth() -> dict[str, GrowthBenchmark]:
    return {
        k: GrowthBenchmark(
            revenue_growth=v["revGrowth"],
            ebit_margin_improvement=v["ebitMarginImpr"],
            depreciation_pct=v["daaPct"],
            capex_pct=v["capexPct"],
            working_capital_pct=v["nwcPct"],
            terminal_growth=v["termGrowth"],
        )
        for k, v in _raw()["industry_growth"].items()
    }


@lru_cache
def sectors() -> tuple[str, ...]:
    return tuple(_raw()["sectors"])


@lru_cache
def geographies() -> tuple[str, ...]:
    return tuple(_raw()["geographies"])


@lru_cache
def stages() -> tuple[str, ...]:
    return tuple(_raw()["stages"])
