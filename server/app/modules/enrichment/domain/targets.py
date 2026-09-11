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
