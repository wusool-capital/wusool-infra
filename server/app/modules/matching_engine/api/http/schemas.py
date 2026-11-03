"""Request/response models for the web find-match API. Every route has one of
these as its `response_model`, so the OpenAPI spec the client is generated
from carries no untyped JSON."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.matching_engine.domain.matching.deals import DealResolution
from app.modules.matching_engine.domain.matching.run_state import RunState


class _Schema(BaseModel):
    # A defaulted field is still always present in responses, so the client sees it as required.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


CriterionName = Literal["vertical", "geography", "ticket_band", "ebitda"]
ApiErrorCode = Literal[
    "unauthorized",
    "web_disabled",
    "not_found",
    "already_reviewed",
    "existing_deals",
    "partial_write",
    "run_not_ready",
]
DiscoveryStatus = Literal[
    "not_needed", "available", "running", "done", "skipped", "unavailable", "failed"
]
ExportField = Literal[
    "rank",
    "origin",
    "seller",
    "seller_attio_id",
    "match_score",
    "data_confidence",
    "status",
    "why_it_matches",
    "why_chosen_over_alternatives",
    "recommended_pitch",
    "risks_and_gaps",
    "source_url",
]


class DiscrepancyRead(_Schema):
    criterion: CriterionName
    stored: str
    stated: str | None = None


class ContextReadingRead(_Schema):
    """What the advisor's note was read as; amounts are absolute USD."""

    verticals: list[str] = []
    region: str | None = None
    countries: list[str] = []
    ticket_low: float | None = None
    ticket_high: float | None = None
    ebitda_low: float | None = None
    ebitda_high: float | None = None
    ev_ceiling: float | None = None
    revenue_low: float | None = None
    revenue_high: float | None = None
    seller_status: list[str] = []


class PreflightRequest(_Schema):
    advisor_context: str | None = Field(default=None, max_length=4000)


class PreflightResponse(_Schema):
    buyer_role_id: str
    conflicts: list[DiscrepancyRead]
    missing: list[DiscrepancyRead]
    # False when the note couldn't be read, so conflicts may be unflagged.
    context_checked: bool
    context: ContextReadingRead


class StartRunRequest(_Schema):
    buyer_role_id: uuid.UUID
    advisor_context: str | None = Field(default=None, max_length=4000)
    # One per "Run match" attempt; a retry or double submit with it returns the same run.
    request_id: uuid.UUID | None = None


class StartRunResponse(_Schema):
    run_id: uuid.UUID


class MoneyRead(_Schema):
    amount: float
    currency: str


class SellerProfileRead(_Schema):
    description: str | None
    hq_country: str | None
    sector_focus: list[str]
    website: str | None
    employee_range: str | None
    founded_year: int | None
    location_count: int | None
    est_revenue: MoneyRead | None
    est_ebitda: MoneyRead | None


class CriterionRead(_Schema):
    criterion: str
    criterion_type: Literal["hard", "soft"]
    result: str
    data_backing: str


class HardRequirementRead(_Schema):
    criterion: str
    value: str | None
    source: str
    human_confirmed: bool


class MandateRead(_Schema):
    """Slack's "Buyer & Mandate" section of View Full Analysis."""

    strategic_thesis: str | None
    ideal_target: str | None
    hard_requirements: list[HardRequirementRead]


class CandidateRead(_Schema):
    id: uuid.UUID
    rank: int
    origin: Literal["crm", "discovery"]
    seller_org_name: str
    seller_attio_id: str | None
    source_url: str | None
    match_score: float | None
    data_confidence: float | None
    why_it_matches: str | None
    why_chosen_over_alternatives: str | None
    recommended_pitch: str | None
    risks_and_gaps: str | None
    status: str
    decision: str | None
    decided_at: datetime | None
    deal_attio_id: str | None
    profile: SellerProfileRead | None
    criteria: list[CriterionRead]


class DiscoveryRead(_Schema):
    status: DiscoveryStatus
    message: str | None = None
    notes: list[str] = []


class RunDetailResponse(_Schema):
    run_id: uuid.UUID
    buyer_role_id: str
    buyer_org_name: str
    state: RunState
    started_at: datetime
    completed_at: datetime | None
    error: str | None
    candidates_considered: int | None
    candidates_filtered: int | None
    # True once a completed run's best CRM score is below `discovery_threshold`.
    low_match_quality: bool
    discovery_threshold: float
    notes: list[str]
    discovery: DiscoveryRead
    candidates: list[CandidateRead]
    mandate: MandateRead | None


class ApproveRequest(_Schema):
    resolution: DealResolution | None = None
    existing_deal_id: str | None = None


class DecisionResponse(_Schema):
    candidate: CandidateRead
    # Set when Slack will receive a research proposal for this seller, as Slack approvals do.
    research_channel_id: str | None = None


class ExistingDealRead(_Schema):
    attio_id: str
    name: str
    stage: str | None
    web_url: str | None


class ApiError(_Schema):
    code: ApiErrorCode
    message: str
    existing_deals: list[ExistingDealRead] = []


class ApiErrorResponse(_Schema):
    detail: ApiError
