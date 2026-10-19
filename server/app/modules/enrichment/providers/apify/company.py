"""Apify implementation of `CompanyDataClient` for a LinkedIn company page —
the last step of the structured waterfall, so Diffbot/PDL answer first.
Needs the company's own LinkedIn URL: searching by name is unreliable.
"""

from datetime import date

from app.modules.enrichment.application.ports.company_data import (
    CompanyDataField,
    CompanyDataResult,
)
from app.modules.enrichment.domain.employee_bands import bucket_employee_count
from app.modules.enrichment.domain.field_plans import EnrichableField
from app.modules.enrichment.domain.linkedin import LINKEDIN_PROVIDER_NAME
from app.modules.enrichment.domain.proposals import FieldValue
from app.modules.enrichment.providers.apify.client import ApifyClient
from app.modules.enrichment.providers.apify.schemas import (
    COMPANY_ACTOR,
    ApifyCompanyItem,
    CompanyInput,
)

# Runs inside a Slack-facing proposal, so it gets a short leash.
_RUN_TIMEOUT_S = 20


def _map_company(
    item: ApifyCompanyItem, requested: set[str], source_url: str
) -> list[CompanyDataField]:
    resolved: list[CompanyDataField] = []

    def _add(field_name: str, value: FieldValue | None) -> None:
        if field_name in requested and value is not None:
            resolved.append(
                CompanyDataField(
                    field_name=field_name,
                    value=value,
                    source_url=source_url,
                    provider=LINKEDIN_PROVIDER_NAME,
                )
            )

    _add("description", (item.description or "").strip() or None)
    # `logo` is deliberately not mapped: it is a signed LinkedIn CDN URL that
    # expires within weeks, so saving it would leave a broken logo in the CRM.
    if item.foundedOn and item.foundedOn.year:
        # Year-only precision, stored as 1 January the way `foundation_date`
        # expects a full date.
        _add("foundation_date", date(item.foundedOn.year, 1, 1))
    hq = next((loc for loc in item.locations if loc.headquarter), None)
    if hq and hq.parsed:
        # The location's bare `country` is an ISO code. `parsed.country` is the
        # short English name, matching what Diffbot proposes.
        _add("hq_country", hq.parsed.country or hq.parsed.countryFull)
    if item.employeeCount is not None:
        _add("employee_range", bucket_employee_count(item.employeeCount))
    return resolved


class ApifyLinkedInCompanyClient:
    def __init__(self, token: str) -> None:
        self._client = ApifyClient(token)

    async def lookup(
        self,
        *,
        org_name: str,
        fields: tuple[EnrichableField, ...],
        domain: str | None = None,
        linkedin_url: str | None = None,
    ) -> CompanyDataResult:
        if not linkedin_url:
            return CompanyDataResult(fields=[])
        items = await self._client.run(
            actor=COMPANY_ACTOR,
            actor_input=CompanyInput(companies=[linkedin_url]),
            item_type=ApifyCompanyItem,
            run_timeout_s=_RUN_TIMEOUT_S,
        )
        if not items:
            return CompanyDataResult(fields=[])
        item = items[0]
        return CompanyDataResult(
            fields=_map_company(item, {f.name for f in fields}, item.linkedinUrl or linkedin_url),
            website=item.website,
        )
