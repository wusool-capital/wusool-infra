"""The provider-agnostic seam `EnrichMixin` depends on for structured
company-data lookups (Diffbot, People Data Labs, ...) — distinct from
`ResearchClient`: that Port returns free-text documents for the LLM to
extract from, this one returns already-typed field values a vendor's own
database resolved directly, no LLM extraction step needed for whatever it
resolves. Never imports a vendor SDK/schema here — swapping or adding a
provider later means writing a new implementation of this Protocol, not
touching `EnrichMixin`.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from app.modules.enrichment.domain.field_plans import EnrichableField


@dataclass(frozen=True)
class CompanyDataField:
    field_name: str
    value: Any
    source_url: str
    provider: str


class CompanyDataClient(Protocol):
    async def lookup(
        self, *, org_name: str, fields: tuple[EnrichableField, ...]
    ) -> list[CompanyDataField]:
        """Returns an entry only for a field this provider actually
        resolved for `org_name` — never a guess, never an entry for a field
        not in `fields`. Fails soft (returns `[]`) on any provider error;
        `EnrichMixin` treats "no answer" and "provider down" identically.
        """
        ...
