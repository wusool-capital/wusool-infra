"""What one discovery run did, in framework-free terms the caller can render."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.modules.discovery.domain.drafts import DraftValue, SellerDraft
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
class ReviewValue:
    field_name: str
    value: DraftValue
    confidence: float
    rationale: str


@dataclass(frozen=True)
class UnverifiedSeller:
    """Not written: a provider's website didn't match (or couldn't be checked
    against) Google Maps', so its fields may describe another company."""

    draft: SellerDraft
    maps_website: str | None
    # (provider, website it matched) per provider that contributed fields.
    provider_websites: tuple[tuple[str, str | None], ...]
    values: tuple[ReviewValue, ...]
    # Set once stored, so the card's button can load the draft back by it.
    review_id: str | None = None


@dataclass(frozen=True)
class PossibleDuplicate:
    lead: DiscoveredLead
    existing_org_name: str


@dataclass(frozen=True)
class FailedLead:
    lead: DiscoveredLead
    reason: str
    # What already reached the CRM before the failure (e.g. Attio, not Postgres).
    landed: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryOutcome:
    status: DiscoveryStatus
    created: tuple[CreatedSeller, ...] = ()
    possible_duplicates: tuple[PossibleDuplicate, ...] = ()
    needs_review: tuple[UnverifiedSeller, ...] = ()
    failed: tuple[FailedLead, ...] = ()
    already_in_crm: int = 0
    # Leads skipped because an earlier run already flagged them for review.
    awaiting_review: int = 0
