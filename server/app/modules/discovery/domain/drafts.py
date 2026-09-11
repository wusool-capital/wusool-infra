"""A `DiscoveredLead` turned into field values ready to prefill `/add-seller`'s
form — in Postgres's own value shape (matching what
`ddl_commands`'s `extract_field_value` returns), never Attio's write shape.
"""

from dataclasses import dataclass, field
from typing import Any

from app.modules.discovery.domain.leads import DiscoveredLead


@dataclass(frozen=True)
class SellerDraft:
    org_name: str
    values: dict[str, Any] = field(default_factory=dict)
    source_urls: tuple[str, ...] = ()


def draft_from_lead(lead: DiscoveredLead) -> SellerDraft:
    """`lead.address` is a street address, not a country — there is no
    organization field it maps onto, so it isn't prefilled at all (rather
    than being stuffed into the wrong one). `category` is a free-text
    Google Maps business type; it's offered as a `sector_focus` guess, but
    the add-form's prefill normalization silently drops it if it isn't one
    of the fixed sector options.
    """
    values: dict[str, Any] = {}
    if lead.category:
        values["sector_focus"] = [lead.category]
    return SellerDraft(org_name=lead.name, values=values, source_urls=(lead.source_url,))
