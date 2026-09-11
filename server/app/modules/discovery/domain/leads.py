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
