"""What one discovery run did, in framework-free terms the caller can render."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.modules.discovery.domain.leads import DiscoveredLead

DiscoveryStatus = Literal["ok", "disabled", "daily_cap_reached"]


class SellerWriteError(Exception):
    """A lead could not be written; `landed` lists what already reached the CRM."""

    def __init__(self, message: str, landed: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.landed = landed


@dataclass(frozen=True)
class CreatedSeller:
    seller_role_id: UUID
    org_attio_id: str
    org_name: str
    source_url: str
    place_id: str | None = None
    enriched_fields: tuple[str, ...] = ()
    enrichment_timed_out: bool = False


@dataclass(frozen=True)
class PossibleDuplicate:
    lead: DiscoveredLead
    existing_org_name: str


@dataclass(frozen=True)
class FailedLead:
    lead: DiscoveredLead
    reason: str


@dataclass(frozen=True)
class DiscoveryOutcome:
    status: DiscoveryStatus
    created: tuple[CreatedSeller, ...] = ()
    possible_duplicates: tuple[PossibleDuplicate, ...] = ()
    failed: tuple[FailedLead, ...] = ()
    already_in_crm: int = 0
