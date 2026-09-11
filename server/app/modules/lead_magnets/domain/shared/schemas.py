"""Pydantic models for every JSON-shaped value crossing a seam inside this
module: what's stored in `tool_runs.payload`, what Bedrock returns, and the
bundled inputs to `attio_values.py`'s per-tool `*_values()` functions.

The one explicit, scoped exception to this module's "no pydantic in
domain/application" rule — see `tests/test_architecture.py`'s allowlist,
which permits `pydantic` only for a file at exactly this path. Nothing
downstream (`pipelines.py`, `valuation_ai.py`, `attio_values.py`,
`providers/bedrock/client.py`) needs to import `pydantic` itself to use
these — only this one file does, so the allowlist stays narrow.

Two families here, deliberately validated differently:

- **Stored-payload models** (`BenchmarkPayload`, `ReadinessPayload`,
  `ValuationPayload`, `BuyerNetworkPayload`) parse `tool_runs.payload` back
  out — `payload.get(key)` plus a manual `isinstance` check per field (the
  `num()`/`text()`/`count()` closures `pipelines.py` used to repeat once
  per tool) is exactly the class of bug Pydantic exists to remove.
  Deliberately permissive (`extra="ignore"`, no min/max/`ge`/`le`
  constraints re-declared from `api/schemas.py`): the data was already
  strictly validated once, at the API boundary, before it was stored, and
  the stored dict also picks up the write contract's own bookkeeping keys
  later (`stage`, `ai`, `attio`, readiness's `score`) that these models
  were never meant to reject.

- **Bedrock response models** (`EnrichResult`, `AnalyzeResult`,
  `SearchQueries`, `CompareResult`, `ReadinessResult`, `InternalNote`) are
  the opposite: strict, no `extra="ignore"`, matching exactly what each
  prompt asks the model for. These used to live in `providers/bedrock/
  schemas.py` and never leave that layer — `LeadLLMPort`'s methods
  returned an already-validated plain `dict`. They moved here so
  `LeadLLMPort` itself (in `application/`) could return the real model
  instead: `application/` still can't import `providers/`, but both it and
  `providers/bedrock/client.py` can import `domain/`, so this is the one
  place both sides can share the same type without either depending on the
  other. Field names match what the existing tool pages already parse,
  verbatim — `comps`, `overallScore`, `scoreBand`, `dimensions[].insight`,
  `recommendations[].title`/`.detail` — read off the live pages' own
  render code rather than inferred, not renamed to Python convention.

- **`attio_values.py` input models** (`ReadinessValuesInput`,
  `BuyerValuesInput`) bundle what `readiness_values()`/`buyer_values()`
  used to take as several loose keyword arguments into one validated
  object. `benchmark_values()`/`valuation_values()` deliberately keep their
  existing signature (one domain dataclass, already the right type) —
  wrapping an already-correctly-typed single argument in another model
  would be ceremony, not safety.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.readiness.readiness import AdvisoryContent


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore")


class BenchmarkPayload(_Payload):
    """Mirrors `BenchmarkInputs`' own fields exactly — everything
    `benchmark_inputs()`/`Pipelines._benchmark()` reads from the stored
    payload."""

    mode: Literal["sme", "tech"] = "sme"
    peer_key: str = ""
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


class ReadinessAnswersPayload(_Payload):
    q1: int | None = None
    q2: int | None = None
    q3: int | None = None
    q4: int | None = None
    q5: int | None = None
    q6: int | None = None
    q7: int | None = None
    q8: int | None = None
    q9: int | None = None
    q10: int | None = None
    q11: int | None = None
    q12: int | None = None
    q13: int | None = None
    q14: str | None = None
    q15: str | None = None


class ReadinessPayload(_Payload):
    name: str = ""
    company: str = ""
    sector: str = ""
    revenue: str | None = None
    country: str | None = None
    answers: ReadinessAnswersPayload = ReadinessAnswersPayload()


class ValuationCompPayload(_Payload):
    co: str = ""
    tk: str = ""
    ev: float | None = None
    rev: float | None = None
    ebitda: float | None = None


class ValuationDiscountsPayload(_Payload):
    revenue_discount_pct: float | None = None
    ebitda_discount_pct: float | None = None


class ValuationPayload(_Payload):
    revenue: float = 0.0
    profit_before_tax: float | None = None
    owner_salary: float | None = None
    sector: str | None = None
    geography: str | None = None
    stage: str | None = None
    cash: float = 0.0
    debt: float = 0.0
    comps: list[ValuationCompPayload] = []
    discounts: ValuationDiscountsPayload | None = None


class BuyerNetworkPayload(_Payload):
    org_name: str = ""
    org_type: list[str] = []
    sector_focus: list[str] = []
    target_geography: list[str] = []
    check_size_min: float | None = None
    check_size_max: float | None = None
    prior_gcc_acquisition: str | None = None


# ===== Bedrock response models — see the module docstring =====


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


class ComparablesResult(BaseModel):
    """`ValuationAi.compare()`'s own composed result — `select_comparables`'s
    Bedrock-sourced comps plus whatever the static sector set filled in to
    reach the target count. Same shape as `api/schemas.py`'s
    `CompareResponse`, defined separately since `application/` can't import
    `api/`."""

    comps: list[Comparable]
    sourced: int
    filled_from_static: int


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


# ===== attio_values.py input models — see the module docstring =====


class ReadinessValuesInput(BaseModel):
    # `AdvisoryContent` is a plain frozen dataclass, not a pydantic model —
    # `arbitrary_types_allowed` accepts it as-is rather than forcing domain/
    # value objects to become pydantic too.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    score: float
    band: str
    advisory: AdvisoryContent
    revenue_usd: float | None = None


class BuyerValuesInput(BaseModel):
    check_size_min: float | None = None
    check_size_max: float | None = None
    prior_gcc_acquisition: str | None = None
    target_geography: list[str] = Field(default_factory=list)
    qualification_note: str | None = None
