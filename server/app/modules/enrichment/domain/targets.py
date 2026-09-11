"""Which existing buyer/seller row a proposal is for. No ORM/Pydantic type
crosses into `domain/` — a plain identifier the ports resolve against.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class EnrichmentTargetKind(StrEnum):
    BUYER = "buyer"
    SELLER = "seller"


@dataclass(frozen=True)
class EnrichmentTarget:
    kind: EnrichmentTargetKind
    role_id: UUID
    org_attio_id: str
    org_name: str


@dataclass(frozen=True)
class ResolvedOrgRole:
    """A resolved `/enrich` candidate, read side — an org plus which of its
    roles (seller/buyer) are active, for the Slack layer to pick from
    before it has committed to one `EnrichmentTarget`.
    """

    org_attio_id: str
    org_name: str
    role_id: str
    kind: str  # "seller" | "buyer"
