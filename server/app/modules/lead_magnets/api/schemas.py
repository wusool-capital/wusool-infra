"""Request and response shapes for the lead-magnet endpoints.

Paths and payloads follow the migration spec's endpoint table, not this
module's own invention:

    POST /enrich           {domain} -> {description, sector}
    POST /analyze          -> {pros[3], cons[3], insights[], fundraise{}}
    POST /compare          -> {comps:[{co,tk,ev,rev,ebitda}]}
    POST /readiness/score  -> {overallScore, scoreBand, summaryParagraph,
                               dimensions[5], recommendations[3]}
    POST /buyer/apply      -> {ok, run_id}
    POST /benchmark        -> the benchmark result (no model involved)

`/benchmark` keeps the path the live tool already posts to
(`wusool-benchmark.html`'s `CFG.relay`), so repointing the page is a host
change rather than a path change. It is absent from the spec's table because
that table lists the *AI* endpoints and the benchmark uses none.

Response field names are the ones the existing pages parse — `comps`,
`overallScore`, `dimensions[].insight` — and are not renamed.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.lead_magnets.domain.benchmark.benchmark_dataset import SECTORS, STAGES
from app.modules.lead_magnets.domain.benchmark.benchmark_narrative import Tone


class _Strict(BaseModel):
    # A misspelled field from a page we are rewriting should fail loudly here
    # rather than be silently dropped and score as a blank.
    model_config = ConfigDict(extra="forbid")


class ReadinessAnswersIn(_Strict):
    """q1-q13 are 0-3 scores; q14 and q15 are free text.

    Every one is optional: the form gates per section, so a partial
    submission is a real shape — and a missing answer must stay missing
    rather than become a zero, which is the hard DEAL RISK flag.
    """

    q1: int | None = Field(default=None, ge=0, le=3)
    q2: int | None = Field(default=None, ge=0, le=3)
    q3: int | None = Field(default=None, ge=0, le=3)
    q4: int | None = Field(default=None, ge=0, le=3)
    q5: int | None = Field(default=None, ge=0, le=3)
    q6: int | None = Field(default=None, ge=0, le=3)
    q7: int | None = Field(default=None, ge=0, le=3)
    q8: int | None = Field(default=None, ge=0, le=3)
    q9: int | None = Field(default=None, ge=0, le=3)
    q10: int | None = Field(default=None, ge=0, le=3)
    q11: int | None = Field(default=None, ge=0, le=3)
    q12: int | None = Field(default=None, ge=0, le=3)
    q13: int | None = Field(default=None, ge=0, le=3)
    q14: str | None = Field(default=None, max_length=2000)
    q15: str | None = Field(default=None, max_length=2000)


class ReadinessRequest(_Strict):
    submission_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    sector: str = Field(min_length=1, max_length=200)
    revenue: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    # Optional by decision: the live tools reject a blank domain outright,
    # which loses the lead. Here it only weakens deduplication.
    domain: str | None = Field(default=None, max_length=253)
    answers: ReadinessAnswersIn


class DimensionOut(BaseModel):
    name: str
    score: float
    insight: str


class RecommendationOut(BaseModel):
    title: str
    detail: str


class ReadinessResponse(BaseModel):
    run_id: str
    overallScore: float
    scoreBand: str
    summaryParagraph: str
    dimensions: list[DimensionOut]
    recommendations: list[RecommendationOut]


class BenchmarkRequest(_Strict):
    """The raw form figures, in USD.

    The live page computes its own score and posts the result; here the
    server computes it, which is the point of the migration — the browser
    stops being the source of truth for what lands in the CRM.
    """

    submission_id: str = Field(min_length=1, max_length=64)
    mode: Literal["sme", "tech"] = "sme"
    # A sector key in SME mode, a funding stage in startup mode.
    peer_key: str = Field(min_length=1, max_length=64)
    company: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    domain: str | None = Field(default=None, max_length=253)
    geography: str | None = Field(default=None, max_length=100)
    consent: bool = False

    revenue: float | None = Field(default=None, ge=0)
    prev_revenue: float | None = Field(default=None, ge=0)
    ebitda_reported: float | None = None
    owner_salary: float | None = Field(default=None, ge=0)
    salary_deducted: bool = False
    gross_margin_pct: float | None = Field(default=None, ge=-100, le=100)
    headcount: int | None = Field(default=None, ge=0)
    rent_cost: float | None = Field(default=None, ge=0)
    capital_raised: float | None = Field(default=None, ge=0)
    top_customer_pct: float | None = Field(default=None, ge=0, le=100)
    recurring_pct: float | None = Field(default=None, ge=0, le=100)
    years_active: float | None = Field(default=None, ge=0)
    outlets: int | None = Field(default=None, ge=0)
    days_to_get_paid: int | None = Field(default=None, ge=0)

    @field_validator("peer_key")
    @classmethod
    def known_peer_cut(cls, value: str) -> str:
        """A sector or stage the dataset has no anchors for would otherwise
        surface as a 500 from the scoring engine. Rejecting it here gives the
        page a 422 naming the field."""
        if value in SECTORS or value in STAGES:
            return value
        raise ValueError(
            f"unknown peer_key {value!r}; expected one of "
            f"{sorted(SECTORS)} (sme) or {sorted(STAGES)} (tech)"
        )


class MetricOut(BaseModel):
    label: str
    value: float | None
    percentile: float | None
    quartile: int | None
    peer_median: float | None


class FlagOut(BaseModel):
    tone: Tone
    title: str
    body: str


class ImpliedEvOut(BaseModel):
    low: float
    mid: float
    high: float
    forward_revenue: float


class BenchmarkResponse(BaseModel):
    run_id: str
    score: int
    band: str
    quartile: int
    peer_label: str
    revenue_band: str
    sample_size: int | None
    metrics: dict[str, MetricOut]
    flags: list[FlagOut]
    data_completeness: int
    metrics_covered: int
    metrics_total: int
    implied_ev: ImpliedEvOut | None
    # Currency is stated on the wire so no consumer has to infer it from a
    # field name — the legacy `*_aed` slugs hold USD and that has already
    # cost one round of confusion.
    currency: Literal["USD"] = "USD"


class EnrichRequest(_Strict):
    """`/enrich` runs as the visitor types their website address."""

    domain: str = Field(min_length=3, max_length=253)
    company: str | None = Field(default=None, max_length=200)


class EnrichResponse(BaseModel):
    description: str
    sector: str


class AnalyzeRequest(_Strict):
    company: str = Field(min_length=1, max_length=200)
    domain: str = Field(default="", max_length=253)
    sector: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)
    geography: str = Field(default="", max_length=100)
    revenue: float = Field(default=0, ge=0)
    ebitda: float = 0
    website_text: str = Field(default="", max_length=20_000)


class CompareRequest(_Strict):
    company: str = Field(min_length=1, max_length=200)
    sector: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)
    revenue: float = Field(default=0, ge=0)
    geography: str = Field(default="", max_length=100)


class ComparableOut(BaseModel):
    co: str
    tk: str
    ev: float | None = None
    rev: float | None = None
    ebitda: float | None = None


class CompareResponse(BaseModel):
    """The response key stays `comps` — the page reads `parsed.comps` in
    three places and around thirty identifiers use the word."""

    comps: list[ComparableOut]
    # How much of the table was actually researched versus filled from
    # sector data, so the report can say so rather than implying all of it
    # was sourced.
    sourced: int
    filled_from_static: int


class BuyerApplyRequest(_Strict):
    """The Buyer Network form's nine fields plus consent.

    `org_type` and `target_geography` are **not** validated here — like
    `BenchmarkRequest.peer_key`, they map onto CRM select options, but
    unlike it they are not needed to compute anything the visitor sees. The
    lead is recorded first; an unmapped value only fails the background
    Attio write (`UnmappedOrgTypeError`/`UnmappedTargetGeographyError`),
    caught by `submit.py` the same way `UnmappedSectorError` is for every
    other tool's sector field. Blocking the record on a CRM-vocabulary typo
    would be the exact lead-loss bug this migration exists to fix.

    `check_size_min`/`check_size_max` are two numbers, not one bucket — the
    live Slack `/add-buyer` form (`ddl_commands/api/buyers.py`, verified
    live 2026-08-30) is the authoritative precedent, and `typical_check_size`
    (a coarse bucket) was deliberately dropped from the schema in
    migration `a4f9e61c3d78` in favour of these two real USD figures.

    `full_name` and `linkedin_url` have nowhere to go in Attio yet: no
    `person` write path exists for any tool in this module today (a
    pre-existing gap, not new here) — they land in `tool_runs.payload` for
    the record, same as every other tool's `name` field.
    """

    submission_id: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=200)
    org_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    org_type: list[str] = Field(min_length=1)
    target_geography: list[str] = Field(min_length=1)
    sector_focus: list[str] = Field(min_length=1)
    check_size_min: float | None = Field(default=None, ge=0)
    check_size_max: float | None = Field(default=None, ge=0)
    prior_gcc_acquisition: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    # Optional by the same decision as every other tool: a blank domain only
    # weakens dedup, never loses the lead.
    domain: str | None = Field(default=None, max_length=253)
    consent: bool = Field(...)

    @field_validator("consent")
    @classmethod
    def consent_given(cls, value: bool) -> bool:
        if not value:
            raise ValueError("consent is required")
        return value


class BuyerApplyResponse(BaseModel):
    ok: bool
    run_id: str
