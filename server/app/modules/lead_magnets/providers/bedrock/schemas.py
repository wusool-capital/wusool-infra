"""Response schemas for the lead-magnet model calls.

Field names match what the existing tool pages already parse, verbatim —
`comps`, `overallScore`, `scoreBand`, `dimensions[].insight`, and
`recommendations[].title`/`.detail`, all read back from the live pages'
own render code rather than inferred. They are not renamed to
Python conventions: the page reads `parsed.comps` in three places and around
thirty identifiers use that word, and the migration's whole promise is that
the visitor sees the same four tools throughout.

These models never leave `providers/` — `application/` receives an
already-validated plain `dict`, the same contract `meetings` keeps.
"""

from typing import Literal

from pydantic import BaseModel, Field


class EnrichResult(BaseModel):
    description: str
    sector: str


class TitledPoint(BaseModel):
    """A strength, risk or insight. An object, not a string — the page renders
    the title and the body separately, and the prompt asks for 8-15 word
    titles against 40-60 word bodies."""

    title: str
    body: str


class ScoredDimension(BaseModel):
    score: float
    note: str


class FundraiseScores(BaseModel):
    """The M&A readiness scorecard the valuation page renders.

    Three scored dimensions plus an overall grade. The prompt is explicit
    that a missing figure scores 50 and says what is missing, rather than
    the model inventing growth or retention metrics it was never given.
    """

    revenue_scale: ScoredDimension
    profitability: ScoredDimension
    market_context: ScoredDimension
    overall_grade: str
    overall_label: str
    summary: str


class SectorJudgement(BaseModel):
    """The analyst's verdict on the auto-assigned tag. `poor` means the
    closest available option would mislead the valuation."""

    sector_fit: Literal["good", "poor"]
    closest_existing_sector: str
    effective_sector: str
    rationale: str


class Discounts(BaseModel):
    revenue_discount_pct: float
    ebitda_discount_pct: float


class DcfOverrides(BaseModel):
    """Sector assumptions the analyst overrides, replacing the static
    benchmark. Field names are the page's own."""

    revGrowth: float
    ebitMarginImpr: float
    daaPct: float
    capexPct: float
    nwcPct: float
    termGrowth: float


class AnalyzeResult(BaseModel):
    """Sector judgement, discounts, DCF overrides, dataset matching terms,
    the strategic read and the readiness scorecard.

    Merging the strategic read into this one call fixes a real bug: the
    preview and the full report were generated independently, so the preview
    could claim a strength the report never mentioned.
    """

    sector_fit: Literal["good", "poor"]
    closest_existing_sector: str = ""
    effective_sector: str = ""
    rationale: str = ""
    discounts: Discounts
    dcf: DcfOverrides
    transaction_search_terms: list[str] = Field(default_factory=list)
    vc_search_terms: list[str] = Field(default_factory=list)
    pros: list[TitledPoint] = Field(min_length=3, max_length=3)
    cons: list[TitledPoint] = Field(min_length=3, max_length=3)
    insights: list[TitledPoint] = Field(min_length=1)
    fundraise: FundraiseScores


class SearchQueries(BaseModel):
    """Pass one of the comparables pipeline. Queries only — asked for
    candidate companies as well, the cheap model confidently returned a
    property developer and an insurance company as comparables for an
    interior fit-out business, with invented tickers.
    """

    queries: list[str] = Field(min_length=1, max_length=6)


class Comparable(BaseModel):
    co: str
    tk: str
    ev: float | None = None
    rev: float | None = None
    ebitda: float | None = None


class CompareResult(BaseModel):
    comps: list[Comparable]


# The five bands the live prompt asks for, verbatim. `index.js`'s BAND_MAP
# translates these to the Attio option titles (Early / Early / Developing /
# Sale Ready / Market Ready) — see `domain/readiness.py`.
ScoreBand = Literal["Not Ready", "Early Stage", "Getting There", "Nearly Ready", "Exit Ready"]


class ReadinessDimension(BaseModel):
    name: str
    score: float
    # `insight`, not `commentary` — the live page reads `dim.insight`.
    insight: str


class ReadinessRecommendation(BaseModel):
    """An object, not a string: the page renders a title and a detail
    separately into each recommendation card."""

    title: str
    detail: str


class ReadinessResult(BaseModel):
    overallScore: float
    scoreBand: ScoreBand
    summaryParagraph: str
    dimensions: list[ReadinessDimension] = Field(min_length=5, max_length=5)
    recommendations: list[ReadinessRecommendation] = Field(min_length=3, max_length=3)


class InternalNote(BaseModel):
    """Internal only — never rendered to the visitor, so a failure here is
    invisible to them.

    One shape, two operations: the readiness advisory note and the buyer
    qualification both produce a priority call plus a paragraph of judgement.
    The `priority` vocabulary differs per caller (`now|6-12 months` for
    readiness), which is why it stays a plain string.
    """

    priority: str
    note: str
