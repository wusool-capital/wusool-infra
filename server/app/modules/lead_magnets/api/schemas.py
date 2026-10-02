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
    POST /submit-lead      -> the blended valuation (no model involved)

`/benchmark` and `/submit-lead` keep the paths the live tools already post
to (`wusool-benchmark.html`'s `CFG.relay`; `dopamine-valuation.html`'s
`pushLeadToAttio`), so repointing the pages is a host change rather than a
path change. Both are absent from the spec's table because that table lists
the *AI* endpoints and neither one calls a model to produce its result — the
live page computed its own blend and sent the finished numbers; here the
server recomputes them from the raw inputs and ignores anything else, which
is the point of the migration: the browser stops being the source of truth
for what lands in the CRM.

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
    # A sector key in SME mode, a funding stage in startup mode — the peer
    # cut the score is computed against, not necessarily the CRM sector (see
    # `sector` below).
    peer_key: str = Field(min_length=1, max_length=64)
    # Tech mode's own sector dropdown (`DATA.techSectorList`) is a separate
    # control from the one `peer_key` reads there (the funding stage), and
    # is the only source `sector_focus` can be mapped from for a tech-mode
    # submission — `peer_key` there is a stage string ("seed", "seriesa", ...)
    # that `sector_mapping.py`'s tables have no entry for. `None` in SME
    # mode, where `peer_key` already *is* the CRM sector.
    sector: str | None = Field(default=None, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    # Optional: the only lead-magnet form that asks for one today. Feeds the
    # Attio `person` write (`AttioIdentityPayload.phone`) — see
    # `domain/shared/attio_values.py::person_values`.
    phone: str | None = Field(default=None, max_length=50)
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
    # Optional: only the deterministic fallback's two fundraise-readiness
    # insights need them, and the live tool's own gate collects them
    # earlier in the funnel — a visitor who skipped that step just gets
    # neither insight on fallback, same as the original.
    raised: bool = False
    stage: str | None = Field(default=None, max_length=100)


class TitledPointOut(BaseModel):
    title: str
    body: str


class DiscountsOut(BaseModel):
    revenue_discount_pct: float
    ebitda_discount_pct: float


class DcfOverridesOut(BaseModel):
    """Sector assumptions the analyst overrides. Field names are the page's
    own — see `domain/shared/schemas.py::DcfOverrides`, which this mirrors."""

    revGrowth: float
    ebitMarginImpr: float
    daaPct: float
    capexPct: float
    nwcPct: float
    termGrowth: float


class ScoredDimensionOut(BaseModel):
    score: float
    note: str


class FundraiseScoresOut(BaseModel):
    revenue_scale: ScoredDimensionOut
    profitability: ScoredDimensionOut
    market_context: ScoredDimensionOut
    overall_grade: str
    overall_label: str
    summary: str


class AnalyzeResponse(BaseModel):
    """Every field but `pros`/`cons`/`insights` is optional: a Bedrock
    failure makes `ValuationAi.analyze` fall back to
    `generate_strategic_analysis`'s deterministic pros/cons/insights only
    (its `except` branch), so this response is genuinely partial on
    failure, not absent. Was returned as a schema-free `JsonObject` — a
    client generated from `/openapi.json` would have typed it `unknown`,
    the one endpoint of five not fully typed on the wire.
    """

    sector_fit: Literal["good", "poor"] | None = None
    closest_existing_sector: str | None = None
    effective_sector: str | None = None
    rationale: str | None = None
    discounts: DiscountsOut | None = None
    dcf: DcfOverridesOut | None = None
    transaction_search_terms: list[str] = Field(default_factory=list)
    vc_search_terms: list[str] = Field(default_factory=list)
    pros: list[TitledPointOut]
    cons: list[TitledPointOut]
    insights: list[TitledPointOut]
    fundraise: FundraiseScoresOut | None = None


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


class ValuationDiscountsIn(BaseModel):
    """`/analyze`'s own `discounts` key, round-tripped back in verbatim.
    Both fields are optional: `Pipelines.valuation_inputs` already
    defaults each to 50% when absent, so a visitor who never called
    `/analyze` still gets a valuation."""

    revenue_discount_pct: float | None = None
    ebitda_discount_pct: float | None = None


class ValuationRequest(_Strict):
    """The blended valuation submission — DCF, trading comps, transaction
    comps. Field names match `Pipelines.valuation_inputs`'s stored-payload
    keys exactly (`profit_before_tax`, not `ebitda`: `ValuationInputs`
    itself adds the owner's salary back to get to EBITDA, so the raw input
    it wants is pre-addback profit), which is what lets a sweeper resume
    rebuild identical inputs from this same payload.

    `comps`, `discounts`, `dcf` and the search terms are what the visitor's
    own prior `/compare` and `/analyze` calls returned, sent back verbatim — this endpoint does not
    re-run either. Their absence is the deterministic-fallback case, not an
    error: the same blend a sweeper resume produces with no model in reach.
    """

    submission_id: str = Field(min_length=1, max_length=64)
    company: str = Field(min_length=1, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    domain: str | None = Field(default=None, max_length=253)
    description: str | None = Field(default=None, max_length=4000)
    sector: str | None = Field(default=None, max_length=200)
    geography: str | None = Field(default=None, max_length=100)
    stage: str | None = Field(default=None, max_length=100)
    # Revenue/profit at the visitor's last funding raise — collected by the
    # Gate form's two conditional fields under "Has your company raised
    # funding?", computed client-side, but until now never sent to any
    # endpoint at all. `raised` itself is deliberately not mirrored here —
    # it already reaches `/analyze` for its own fundraise-readiness insight,
    # and the lead record intentionally doesn't duplicate it (same as
    # `AnalyzeRequest.raised`'s own note on this split).
    last_raise_revenue: float | None = Field(default=None, ge=0)
    last_raise_pbt: float | None = None
    revenue: float = Field(ge=0)
    profit_before_tax: float | None = None
    owner_salary: float | None = Field(default=None, ge=0)
    cash: float = Field(default=0, ge=0)
    debt: float = Field(default=0, ge=0)
    comps: list[ComparableOut] = Field(default_factory=list)
    discounts: ValuationDiscountsIn | None = None
    # `/analyze`'s analyst output, echoed back unbounded like `/analyze` emits
    # it — a tighter cap here would 422 and lose the lead.
    dcf: DcfOverridesOut | None = None
    transaction_search_terms: list[str] = Field(default_factory=list)
    vc_search_terms: list[str] = Field(default_factory=list)
    consent: bool = False


class MethodRowOut(BaseModel):
    name: str
    low: float
    mid: float
    high: float


class ValuationResponse(BaseModel):
    run_id: str
    low: float
    mid: float
    high: float
    methods: list[MethodRowOut]


class GetStartedRequest(_Strict):
    """The Get Started form — the site's main CTA, ported off Tally.

    Pure lead capture: nothing is computed and nothing is returned to the
    visitor but an acknowledgement.

    Field names are the integration. `bootstrap.py`'s seller branch validates
    the stored payload with `AttioIdentityPayload`, so `name`, `email`,
    `company`, `domain`, `sector` and `geography` must be spelled exactly
    this way for the organisation and `person` writes to pick them up —
    `name` in particular, not `full_name` (that spelling is the buyer
    branch's, read from `BuyerNetworkPayload`). Renaming any of them stops
    the corresponding Attio write silently, with nothing else failing.

    `geography` rather than `country`: both resolve to
    `organizations.hq_country` with `geography` taking priority, matching
    benchmark and valuation.

    `sell_timeline` is **not** a `Literal` here, for the same reason as
    `BuyerApplyRequest.org_type`: it maps onto a CRM select option but is
    needed to compute nothing the visitor sees, so an unmapped value must
    fail the background Attio write (`UnmappedSellTimelineError`), never the
    record.

    `ebitda` carries no `ge=0` — a loss-making business is a real
    submission, and the benchmark tool's own `ebitda_reported` is unbounded
    for the same reason. `years_active` is an `int`: the mirrored Postgres
    column is `integer` and `attio_sync` reads it with `v.integer`.

    Revenue and EBITDA arrive in **USD**. The page collects AED — the label
    the live Tally form uses — and divides by the peg before posting, the
    same conversion `static/benchmark/30-helpers.js`'s `toCalc` already
    does. Nothing server-side converts.
    """

    submission_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    geography: str = Field(min_length=1, max_length=100)
    sector: str = Field(min_length=1, max_length=200)
    # Free text revealed by the "Other" sector option. Not conditionally
    # required here — the page enforces it, and a blank one must never cost
    # the lead. The endpoint folds it into `description`.
    sector_other: str | None = Field(default=None, max_length=200)
    revenue: float = Field(ge=0)
    ebitda: float
    years_active: int = Field(ge=0)
    sell_timeline: str = Field(min_length=1, max_length=100)
    # Optional by the same decision as every other tool: a blank domain only
    # weakens deduplication, never loses the lead.
    domain: str | None = Field(default=None, max_length=253)
    consent: bool = Field(...)

    @field_validator("consent")
    @classmethod
    def consent_given(cls, value: bool) -> bool:
        if not value:
            raise ValueError("consent is required")
        return value


class GetStartedResponse(BaseModel):
    ok: bool
    run_id: str


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

    `full_name`, `email` and `linkedin_url` feed the Attio `person` write
    (`providers/attio/person_writer.py`, wired in via
    `bootstrap.py::_RoleAttioWriter`) as well as landing in
    `tool_runs.payload`, same as every other tool's `name` field.
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
