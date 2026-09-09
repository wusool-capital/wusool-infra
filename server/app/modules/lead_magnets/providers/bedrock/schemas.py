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
