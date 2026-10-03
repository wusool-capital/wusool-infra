"""The one entry point `matching_engine` calls into — search, pre-filter
against the CRM, auto-create what's new, and report what happened as a typed
`DiscoveryOutcome` the caller renders. `exclude_terms` is opaque here — just
strings a found lead's category/name is filtered against, with no notion of
where they came from (a buyer's `sector_exclusion` requirement, on the
caller's side). `quota_key` is what the per-day search cap counts against.
Exported via this module's root `__all__`.
"""

from app.modules.discovery.api.dependencies import discovery_service
from app.modules.discovery.domain.outcome import DiscoveryOutcome


async def discover_and_create_sellers(
    *, industry: str, geography: str, quota_key: str, exclude_terms: tuple[str, ...] = ()
) -> DiscoveryOutcome:
    return await discovery_service().discover_and_create(
        industry=industry,
        geography=geography,
        quota_key=quota_key,
        exclude_terms=exclude_terms,
    )
