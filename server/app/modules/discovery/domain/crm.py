"""How a discovered lead relates to organizations already in the CRM."""

from dataclasses import dataclass
from enum import StrEnum


class CrmMatchKind(StrEnum):
    # Exact identifiers: safe to skip a lead on their own.
    PLACE_ID = "place_id"
    DOMAIN = "domain"
    # Name similarity alone is too weak to decide unattended; a human does.
    FUZZY_NAME = "fuzzy_name"
    NONE = "none"


@dataclass(frozen=True)
class CrmMatch:
    kind: CrmMatchKind
    org_attio_id: str | None = None
    org_name: str | None = None
