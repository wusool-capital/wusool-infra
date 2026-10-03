"""An unverified seller lead found on the public web, outside the CRM. Moved
here from `matching_engine.domain.web_search.WebSourcedLead` — discovery,
not matching, owns "what sellers exist that we don't have yet".
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveredLead:
    name: str
    source_url: str
    address: str | None = None
    category: str | None = None
    country: str | None = None
    website: str | None = None
    types: tuple[str, ...] = ()
    place_id: str | None = None


def filter_excluded_leads(
    leads: list[DiscoveredLead], exclude_terms: tuple[str, ...]
) -> list[DiscoveredLead]:
    """Drops any lead whose `category`/`name`/`types` case-insensitively
    contains one of `exclude_terms` (e.g. a buyer's `sector_exclusion`
    value) — Google Places' text search has no dependable negation syntax
    to keep these out of the search itself, so this is the only place the
    exclusion can actually take effect. `types` (Places' machine-readable
    categories, e.g. `"general_contractor"`) catches a lead whose display
    name and category never say the excluded word at all.
    """
    if not exclude_terms:
        return leads
    lowered_terms = [term.lower() for term in exclude_terms]

    def _is_excluded(lead: DiscoveredLead) -> bool:
        # Places' `types` are underscore-joined (`"general_contractor"`); a
        # multi-word exclude term like "general contractor" would never
        # substring-match that without the underscore -> space swap.
        spaced_types = " ".join(t.replace("_", " ") for t in lead.types)
        haystack = f"{lead.name} {lead.category or ''} {spaced_types}".lower()
        return any(term in haystack for term in lowered_terms)

    return [lead for lead in leads if not _is_excluded(lead)]
