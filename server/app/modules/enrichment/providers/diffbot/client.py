"""Real Diffbot implementation of `CompanyDataClient`, using the Enhance
API (`GET /kg/v3/enhance`) to look up an `Organization` entity by name.
Structured-field tier of the seller research waterfall — tried before the
free-text `ResearchClient` (Firecrawl) + LLM extraction path, since a
directly-typed field from Diffbot's own database needs no LLM inference.

Field mapping verified against a live account — see `schemas.py`'s
docstring for what changed from the original blind mapping.
"""

import logging
from datetime import date

import aiohttp

from app.modules.enrichment.application.ports.company_data import CompanyDataField
from app.modules.enrichment.domain.employee_bands import bucket_employee_count
from app.modules.enrichment.domain.field_plans import EnrichableField
from app.modules.enrichment.domain.proposals import FieldValue
from app.modules.enrichment.providers.diffbot.schemas import (
    DiffbotEnhanceResponse,
    DiffbotOrganization,
)
from app.modules.enrichment.providers.http_json import fetch_json

logger = logging.getLogger(__name__)

_ENHANCE_URL = "https://kg.diffbot.com/kg/v3/enhance"
_PROVIDER_NAME = "Diffbot"
# A structured lookup, not a scrape — aiohttp's 300s default would leave a
# background enrichment run hanging far longer than a hung Diffbot call is
# ever worth waiting on for one field of nine.
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


def _parse_founding_date(raw: str) -> date | None:
    """Strips Diffbot's leading precision character (`"d2010-01-01"` ->
    `"2010-01-01"`) before parsing.
    """
    digits_start = next((i for i, c in enumerate(raw) if c.isdigit()), None)
    if digits_start is None:
        return None
    try:
        return date.fromisoformat(raw[digits_start : digits_start + 10])
    except ValueError:
        return None


def _map_entity(entity: DiffbotOrganization, requested: set[str]) -> list[CompanyDataField]:
    source_url = entity.origin or "https://www.diffbot.com/"
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

    if entity.foundingDate and entity.foundingDate.text:
        founding_date = _parse_founding_date(entity.foundingDate.text)
        if founding_date is not None:
            _add("foundation_date", founding_date)
            _add("years_active", date.today().year - founding_date.year)

    _add("description", entity.description)
    if entity.location and entity.location.country:
        _add("hq_country", entity.location.country.name)
    _add("linkedin", entity.linkedInUri)
    if entity.revenue and entity.revenue.currency in (None, "USD"):
        # The write path (`app/modules/attio/providers/attio/money.py`) and
        # the extraction prompt both hardcode USD for this field with no FX
        # conversion anywhere in the pipeline — proposing a non-USD figure
        # as-is would silently write the wrong number, so skip it rather
        # than guess at a conversion.
        _add("est_revenue", entity.revenue.value)
    _add("location_count", entity.nbLocations)
    _add("logo_url", entity.logo)
    _add("angellist", entity.angellistUri)
    _add("facebook", entity.facebookUri)
    _add("twitter", entity.twitterUri)

    if entity.nbEmployeesMin is not None:
        band = bucket_employee_count(entity.nbEmployeesMin)
        if band:
            _add("employee_range", band)

    return resolved


class DiffbotCompanyDataClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def lookup(
        self, *, org_name: str, fields: tuple[EnrichableField, ...]
    ) -> list[CompanyDataField]:
        requested = {f.name for f in fields}
        body = await fetch_json(
            url=_ENHANCE_URL,
            params={"token": self._api_key, "type": "Organization", "name": org_name},
            timeout=_REQUEST_TIMEOUT,
            log_prefix="diffbot_lookup",
            org_name=org_name,
        )
        if body is None:
            return []

        try:
            parsed = DiffbotEnhanceResponse.model_validate(body)
        except Exception:
            logger.warning("diffbot_response_unparseable org_name=%s", org_name)
            return []

        if not parsed.data:
            return []
        return _map_entity(parsed.data[0].entity, requested)
