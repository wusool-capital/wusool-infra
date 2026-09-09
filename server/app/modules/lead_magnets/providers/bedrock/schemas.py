"""Response schemas for the lead-magnet model calls.

Field names match what the existing tool pages already parse, verbatim —
`comps`, `overallScore`, `scoreBand` and the rest. They are not renamed to
Python conventions: the page reads `parsed.comps` in three places and around
thirty identifiers use that word, and the migration's whole promise is that
the visitor sees the same four tools throughout.

These models never leave `providers/` — `application/` receives an
already-validated plain `dict`, the same contract `meetings` keeps.
"""

from pydantic import BaseModel, Field


class EnrichResult(BaseModel):
    description: str
    sector: str


class FundraiseScores(BaseModel):
    """Left open: the dimension set comes from the valuation page's own
    fundraise prompt, which has not been ported yet."""

    model_config = {"extra": "allow"}


class AnalyzeResult(BaseModel):
    """The merge of three current calls. Fixing a real bug in the process:
    the preview and the full report were generated independently, so the
    preview could claim a strength the report never mentioned.
    """

    pros: list[str] = Field(min_length=3, max_length=3)
    cons: list[str] = Field(min_length=3, max_length=3)
    insights: list[str]
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


class ReadinessDimension(BaseModel):
    name: str
    score: float
    commentary: str


class ReadinessResult(BaseModel):
    overallScore: float
    scoreBand: str
    summaryParagraph: str
    dimensions: list[ReadinessDimension] = Field(min_length=5, max_length=5)
    recommendations: list[str] = Field(min_length=3, max_length=3)


class BuyerQualification(BaseModel):
    """Internal only — never rendered to the applicant, so a failure here is
    invisible to them."""

    priority: str
    note: str
