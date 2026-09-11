"""A resolved `/enrich` target, read side — an org plus which of its roles
(seller/buyer) are active, for the Slack layer to pick from.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedOrgRole:
    org_attio_id: str
    org_name: str
    role_id: str
    kind: str  # "seller" | "buyer"
