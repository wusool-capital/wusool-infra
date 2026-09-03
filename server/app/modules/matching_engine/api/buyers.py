"""Pydantic schemas at the buyer concept's public boundary — data
definitions only. Wiring (session/repository construction, calling
application services) lives in `dependencies.py`.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer (that representation belongs to a future
higher-level application service, not the persistence/schema layer).
"""

import uuid
from dataclasses import dataclass

from pydantic import BaseModel

from app.modules.matching_engine.application.buyers import BuyerCandidate, ResolutionStatus
from app.modules.utilities.domain.money import Money


class _BuyerCandidateOrg(BaseModel):
    name: str
    hq_country: str | None = None
    sector_focus: list[str] = []


class BuyerSummary(BaseModel):
    id: str
    organization: _BuyerCandidateOrg
    model: str | None = None
    mandate_status: str | None = None

    @classmethod
    def from_candidate(cls, candidate: BuyerCandidate) -> "BuyerSummary":
        return cls(
            id=candidate.id,
            organization=_BuyerCandidateOrg(
                name=candidate.org_name,
                hq_country=candidate.org_hq_country,
                sector_focus=candidate.org_sector_focus,
            ),
            model=candidate.model,
            mandate_status=candidate.mandate_status,
        )


class BuyerRoleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    org_attio_id: str
    model: str | None = None
    mandate_status: str | None = None
    ebitda_floor: Money | None = None
    check_size_min: Money | None = None
    check_size_max: Money | None = None
    ev_ceiling: Money | None = None
    deal_structure_tolerance: str | None = None
    earnout_tolerance: bool | None = None
    profitable_only: bool | None = None
    investment_strategy: str | None = None
    notes: str | None = None
    key_contact_attio_id: str | None = None
    acquisition_enrichment: str | None = None
    deals_introduced: int | None = None
    deals_converted: int | None = None


@dataclass(frozen=True)
class BuyerResolutionRead:
    status: ResolutionStatus
    candidates: list[BuyerSummary] | None = None
