"""Implements `discovery.SellerWriterPort`: the CRM pre-filter lookup and the
headless create for a discovered lead. The create enriches first (basic tier,
in memory), returns the lead for review instead of writing when a provider's
website disagrees with Maps', then does one Attio-first write through
`write_seller_add` — the
same ordering `/add-seller` uses, so `discovery` never touches Attio or
Postgres itself.
"""

import asyncio
import logging
from dataclasses import replace

from pydantic import ValidationError

from app.modules.ddl_commands.api.dependencies import (
    find_organization_by_domains,
    find_organization_by_place_id,
    search_organizations,
)
from app.modules.ddl_commands.api.organizations import (
    ORGANIZATION_FIELDS_BY_NAME,
    OrganizationUpdate,
)
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.seller_write import write_seller_add
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME, SellerUpdate
from app.modules.ddl_commands.api.slack.views.dynamic_fields import normalize_prefill
from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.application.sellers import SellerAlreadyExistsError
from app.modules.discovery import (
    CreatedSeller,
    CrmMatch,
    CrmMatchKind,
    DiscoveredLead,
    ReviewValue,
    SellerDraft,
    SellerWriteError,
    UnverifiedSeller,
)
from app.modules.discovery.domain.drafts import hostname, websites_match
from app.modules.enrichment import BasicEnrichment, ProviderEvidence, propose_basic_seller_fields

logger = logging.getLogger(__name__)

_SELLER_FIELDS_BY_NAME = {**SELLER_ROLE_FIELDS_BY_NAME, **ORGANIZATION_FIELDS_BY_NAME}


def _verified(website: str | None, evidence: tuple[ProviderEvidence, ...]) -> bool:
    return website is not None and all(
        e.website is not None and websites_match(website, e.website) for e in evidence
    )


def _domain_variants(website: str | None) -> list[str]:
    host = hostname(website) if website else None
    return [host, f"www.{host}"] if host else []


class DdlCommandsSellerWriterAdapter:
    def __init__(self) -> None:
        # Process-local, enough for a single instance. One lock, not one per
        # key: two leads can collide on domain while having different place
        # ids, so the re-check and the write must be one critical section.
        # Enrichment (the slow part) runs outside it.
        self._write_lock = asyncio.Lock()

    async def find_existing(self, lead: DiscoveredLead) -> CrmMatch:
        if match := await self._find_exact(lead.place_id, lead.website):
            return match
        if candidates := await search_organizations(lead.name):
            return CrmMatch(CrmMatchKind.FUZZY_NAME, candidates[0].attio_id, candidates[0].name)
        return CrmMatch(CrmMatchKind.NONE)

    @staticmethod
    async def _find_exact(place_id: str | None, website: str | None) -> CrmMatch | None:
        if place_id and (org := await find_organization_by_place_id(place_id)):
            return CrmMatch(CrmMatchKind.PLACE_ID, org.attio_id, org.name)
        if hosts := _domain_variants(website):
            if org := await find_organization_by_domains(hosts):
                return CrmMatch(CrmMatchKind.DOMAIN, org.attio_id, org.name)
        return None

    async def enrich_and_create(
        self, draft: SellerDraft, *, enrichment_timeout_s: float
    ) -> CreatedSeller | UnverifiedSeller:
        enrichment, timed_out = await self._enrich(draft, enrichment_timeout_s)
        enriched = enrichment.values
        merged: dict[str, PrefillValue] = {v.field_name: v.proposed for v in enriched}
        merged.update(draft.values)
        prefill = normalize_prefill(merged, _SELLER_FIELDS_BY_NAME, warn_on_drop=False)
        org_extracted: dict[str, PrefillValue | None] = {
            n: v for n, v in prefill.items() if n in ORGANIZATION_FIELDS_BY_NAME
        }
        role_extracted: dict[str, PrefillValue | None] = {
            n: v for n, v in prefill.items() if n in SELLER_ROLE_FIELDS_BY_NAME
        }
        try:
            OrganizationUpdate.model_validate(org_extracted)
            SellerUpdate.model_validate(role_extracted)
        except ValidationError as exc:
            raise SellerWriteError(f"invalid seller values ({exc.error_count()})") from exc

        domains = draft.values.get("domains")
        website = f"https://{domains[0]}" if isinstance(domains, list) and domains else None
        used = [v for v in enriched if v.field_name in prefill]
        if used and not _verified(website, enrichment.evidence):
            return UnverifiedSeller(
                draft=replace(
                    draft,
                    values={n: v for n, v in prefill.items() if not isinstance(v, dict)},
                ),
                maps_website=domains[0] if isinstance(domains, list) and domains else None,
                provider_websites=tuple((e.provider, e.website) for e in enrichment.evidence),
                values=tuple(
                    ReviewValue(v.field_name, value, v.confidence, v.rationale)
                    for v in used
                    if not isinstance(value := prefill[v.field_name], dict)
                ),
            )
        async with self._write_lock:
            # Re-check under the lock: another lead in this run, or another
            # run, may have created this company since `find_existing` looked.
            if await self._find_exact(draft.source_place_id, website):
                raise SellerWriteError("already in the CRM")
            try:
                role = await write_seller_add(
                    is_new_org=True,
                    org_attio_id=None,
                    org_name=draft.org_name,
                    org_extracted=org_extracted,
                    role_extracted=role_extracted,
                    source_place_id=draft.source_place_id,
                )
            except PartialWriteError as exc:
                raise SellerWriteError(str(exc.cause), landed=tuple(exc.landed)) from exc
            except SellerAlreadyExistsError as exc:
                raise SellerWriteError("seller already exists") from exc

        return CreatedSeller(
            seller_role_id=role.id,
            org_attio_id=role.org_attio_id,
            org_name=draft.org_name,
            source_url=draft.source_urls[0] if draft.source_urls else "",
            place_id=draft.source_place_id,
            enriched_fields=tuple(v.field_name for v in used),
            enrichment_timed_out=timed_out,
        )

    @staticmethod
    async def _enrich(draft: SellerDraft, timeout_s: float) -> tuple[BasicEnrichment, bool]:
        """Never raises: a failed or slow enrichment just leaves the lead
        unenriched, since the write itself must not be lost to it."""
        if timeout_s <= 0:
            return BasicEnrichment(values=()), True
        domains = draft.values.get("domains")
        domain = domains[0] if isinstance(domains, list) and domains else None
        try:
            async with asyncio.timeout(timeout_s):
                values = await propose_basic_seller_fields(
                    org_name=draft.org_name, domain=domain, current_values=dict(draft.values)
                )
        except TimeoutError:
            logger.warning("discovery_enrichment_timed_out org_name=%s", draft.org_name)
            return BasicEnrichment(values=()), True
        except Exception:
            logger.warning("discovery_enrichment_failed org_name=%s", draft.org_name, exc_info=True)
            return BasicEnrichment(values=()), False
        return values, False
