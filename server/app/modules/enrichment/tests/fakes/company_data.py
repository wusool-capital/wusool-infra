"""Fake `CompanyDataClient` for tests — no network calls."""

from app.modules.enrichment.application.ports.company_data import (
    CompanyDataClient,
    CompanyDataField,
    CompanyDataResult,
)
from app.modules.enrichment.domain.field_plans import EnrichableField


class FakeCompanyDataClient(CompanyDataClient):
    def __init__(
        self, fields: list[CompanyDataField] | None = None, website: str | None = None
    ) -> None:
        self.fields = fields or []
        self.website = website
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.domains: list[str | None] = []

    async def lookup(
        self, *, org_name: str, fields: tuple[EnrichableField, ...], domain: str | None = None
    ) -> CompanyDataResult:
        self.domains.append(domain)
        self.calls.append((org_name, tuple(f.name for f in fields)))
        requested = {f.name for f in fields}
        return CompanyDataResult(
            fields=[f for f in self.fields if f.field_name in requested], website=self.website
        )
