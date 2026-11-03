"""Request/response models for the web find-match API. Every route has one of
these as its `response_model`, so the OpenAPI spec the client is generated
from carries no untyped JSON."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.matching_engine.domain.matching.deals import DealResolution
from app.modules.matching_engine.domain.matching.run_state import RunState

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


class DiscrepancyRead(BaseModel):
    criterion: CriterionName
    stored: str
    stated: str | None = None


class ContextReadingRead(BaseModel):
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


class PreflightRequest(BaseModel):
    advisor_context: str | None = Field(default=None, max_length=4000)


class PreflightResponse(BaseModel):
    buyer_role_id: str
    conflicts: list[DiscrepancyRead]
    missing: list[DiscrepancyRead]
    # False when the note couldn't be read, so conflicts may be unflagged.
    context_checked: bool
    context: ContextReadingRead


class StartRunRequest(BaseModel):
    buyer_role_id: uuid.UUID
    advisor_context: str | None = Field(default=None, max_length=4000)


class StartRunResponse(BaseModel):
    run_id: uuid.UUID


class CandidateRead(BaseModel):
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


class DiscoveryRead(BaseModel):
    status: DiscoveryStatus
    message: str | None = None
    notes: list[str] = []


class RunDetailResponse(BaseModel):
    run_id: uuid.UUID
    buyer_role_id: str
    buyer_org_name: str
    state: RunState
    started_at: datetime
    completed_at: datetime | None
    error: str | None
    candidates_considered: int | None
    candidates_filtered: int | None
    # True once a completed run's best CRM score is below the discovery threshold.
    low_match_quality: bool
    notes: list[str]
    discovery: DiscoveryRead
    candidates: list[CandidateRead]


class ApproveRequest(BaseModel):
    resolution: DealResolution | None = None
    existing_deal_id: str | None = None


class DecisionResponse(BaseModel):
    candidate: CandidateRead


class ExistingDealRead(BaseModel):
    attio_id: str
    name: str
    stage: str | None
    web_url: str | None


class ApiError(BaseModel):
    code: ApiErrorCode
    message: str
    existing_deals: list[ExistingDealRead] = []


class ApiErrorResponse(BaseModel):
    detail: ApiError
