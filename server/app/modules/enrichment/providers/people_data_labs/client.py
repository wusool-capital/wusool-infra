"""Real People Data Labs implementation of `CompanyDataClient`, using the
Company Enrichment API (`GET /v5/company/enrich`) to look up a company by
name. Second tier of the seller research waterfall — called only for
fields Diffbot didn't resolve, since PDL's free tier (100 lookups/month) is
the thinner of the two.

Field mapping written against PDL's own published response schema, not
verified live — see `schemas.py`'s docstring. Notably, PDL does not
publish a revenue field on its Company Enrichment API at all — `est_revenue`
is never proposed from this provider.
"""

import logging
from datetime import date

import aiohttp

from app.modules.enrichment.application.ports.company_data import CompanyDataField
from app.modules.enrichment.domain.employee_bands import bucket_employee_count
from app.modules.enrichment.domain.field_plans import EnrichableField
from app.modules.enrichment.domain.proposals import FieldValue
from app.modules.enrichment.providers.http_json import fetch_json
from app.modules.enrichment.providers.people_data_labs.schemas import PdlCompanyResponse

logger = logging.getLogger(__name__)

_ENRICH_URL = "https://api.peopledatalabs.com/v5/company/enrich"
_PROVIDER_NAME = "People Data Labs"
# A structured lookup, not a scrape — same reasoning as Diffbot's own
# `_REQUEST_TIMEOUT` (aiohttp's 300s default would hang a background
# enrichment run far longer than this one field is worth waiting on).
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


def _map_response(parsed: PdlCompanyResponse, requested: set[str]) -> list[CompanyDataField]:
    source_url = parsed.website or "https://www.peopledatalabs.com/"
    resolved: list[CompanyDataField] = []

    def _add(field_name: str, value: FieldValue | None) -> None:
        if field_name in requested and value is not None:
            resolved.append(
                CompanyDataField(
                    field_name=field_name,
                    value=value,
                    source_url=source_url,
                    provider=_PROVIDER_NAME,
                )
            )

    _add("description", parsed.summary)
    _add("linkedin", parsed.linkedin_url)
    if parsed.location:
        _add("hq_country", parsed.location.country)
    if parsed.founded:
        _add("foundation_date", date(parsed.founded, 1, 1))
        _add("years_active", date.today().year - parsed.founded)
    if parsed.estimated_num_employees is not None:
        band = bucket_employee_count(parsed.estimated_num_employees)
        if band:
            _add("employee_range", band)

    return resolved


class PeopleDataLabsCompanyDataClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def lookup(
        self, *, org_name: str, fields: tuple[EnrichableField, ...]
    ) -> list[CompanyDataField]:
        requested = {f.name for f in fields}
        body = await fetch_json(
            url=_ENRICH_URL,
            params={"api_key": self._api_key, "name": org_name},
            timeout=_REQUEST_TIMEOUT,
            log_prefix="people_data_labs_lookup",
            org_name=org_name,
        )
        if body is None:
            return []

        try:
            parsed = PdlCompanyResponse.model_validate(body)
        except Exception:
            logger.warning("people_data_labs_response_unparseable org_name=%s", org_name)
            return []

        return _map_response(parsed, requested)
