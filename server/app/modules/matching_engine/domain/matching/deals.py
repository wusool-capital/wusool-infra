"""Domain values for the deal an approved match becomes."""

from dataclasses import dataclass
from typing import Literal

QUALIFIED_STAGE = "Qualified"
INBOUND_STAGE = "Inbound"

DealResolution = Literal["promote_existing", "create_new"]


@dataclass(frozen=True)
class QualifiedDealDraft:
    name: str
    buyer_attio_id: str
    seller_attio_id: str


@dataclass(frozen=True)
class ExistingDeal:
    attio_id: str
    name: str
    stage: str | None
    web_url: str | None


@dataclass(frozen=True)
class DealRecord:
    """A deal as Postgres should hold it once the approval commits."""

    attio_id: str
    name: str
    stage: str | None
    buyer_attio_id: str
    seller_attio_id: str
