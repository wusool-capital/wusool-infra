"""Search, pre-filter against the CRM, then auto-create what's new.

Replaces the human `/add-seller` step as the dedupe gate: an exact `place_id`
or domain hit skips a lead, a name-only hit is handed back for a human to
decide, and only leads with no CRM match are written — unless their enriched
fields came from a provider whose website disagrees with Maps', in which case
they come back as `UnverifiedSeller` for a human to review.
"""

import asyncio
import logging
from dataclasses import replace

from app.modules.discovery.application.base import ServiceBase
from app.modules.discovery.domain.crm import CrmMatchKind
from app.modules.discovery.domain.drafts import draft_from_lead
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.domain.outcome import (
    CreatedSeller,
    DiscoveryOutcome,
    FailedLead,
    PossibleDuplicate,
    SellerWriteError,
    UnverifiedSeller,
)

logger = logging.getLogger(__name__)

# One Places call returns up to 20 at the same price as 1, so search wide and
# let the CRM pre-filter, not the API, decide which few survive.
_CANDIDATE_POOL = 20


class CreateMixin(ServiceBase):
    async def discover_and_create(
        self,
        *,
        industry: str,
        geography: str,
        quota_key: str,
        exclude_terms: tuple[str, ...] = (),
    ) -> DiscoveryOutcome:
        if self._lead_search_client is None:
            return DiscoveryOutcome(status="disabled")
        if not self._search_limiter.check(quota_key):
            logger.warning("discovery_daily_cap_reached quota_key=%s", quota_key)
            return DiscoveryOutcome(status="daily_cap_reached")

        try:
            leads = await self._lead_search_client.find_potential_sellers(
                industry=industry,
                geography=geography,
                limit=_CANDIDATE_POOL,
                exclude_terms=exclude_terms,
            )
        except Exception:
            # A search that never ran shouldn't use up one of the day's runs.
            self._search_limiter.refund(quota_key)
            raise
        if not leads:
            # The Places client returns [] on a failed call too, and either
            # way nothing was written, so it shouldn't cost a daily run.
            self._search_limiter.refund(quota_key)

        pending = await self._pending_reviews(leads)
        to_create: list[DiscoveredLead] = []
        possible_duplicates: list[PossibleDuplicate] = []
        already_in_crm = 0
        awaiting_review = 0
        for lead in leads:
            if len(to_create) + len(possible_duplicates) >= self._policy.lead_limit:
                break
            match = await self._seller_writer_port.find_existing(lead)
            if match.kind in (CrmMatchKind.PLACE_ID, CrmMatchKind.DOMAIN):
                already_in_crm += 1
            elif match.kind is CrmMatchKind.FUZZY_NAME:
                possible_duplicates.append(
                    PossibleDuplicate(lead=lead, existing_org_name=match.org_name or "")
                )
            elif lead.place_id in pending:
                # Its earlier card still works; don't pay to enrich it again.
                awaiting_review += 1
            else:
                to_create.append(lead)

        created, needs_review, failed = await self._create_all(to_create)
        return DiscoveryOutcome(
            status="ok",
            created=created,
            possible_duplicates=tuple(possible_duplicates),
            needs_review=tuple([await self._store_for_review(u) for u in needs_review]),
            failed=failed,
            already_in_crm=already_in_crm,
            awaiting_review=awaiting_review,
        )

    async def _pending_reviews(self, leads: list[DiscoveredLead]) -> set[str]:
        """Fails open: a store outage re-posts a lead rather than hiding it."""
        try:
            return await self._review_store.pending_place_ids(
                [lead.place_id for lead in leads if lead.place_id]
            )
        except Exception:
            logger.exception("discovery_pending_reviews_lookup_failed")
            return set()

    async def _store_for_review(self, unverified: UnverifiedSeller) -> UnverifiedSeller:
        """Without a stored row the card falls back to a short-lived token, so
        the lead is never lost, only not deduplicated."""
        place_id = unverified.draft.source_place_id
        if place_id is None:
            return unverified
        try:
            await self._review_store.add(unverified)
        except Exception:
            logger.exception("discovery_review_store_failed", extra={"place_id": place_id})
            return unverified
        return replace(unverified, review_id=place_id)

    async def _create_all(
        self, leads: list[DiscoveredLead]
    ) -> tuple[tuple[CreatedSeller, ...], tuple[UnverifiedSeller, ...], tuple[FailedLead, ...]]:
        semaphore = asyncio.Semaphore(self._policy.enrichment_concurrency)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._policy.enrichment_budget_s

        async def _create(lead: DiscoveredLead) -> CreatedSeller | UnverifiedSeller | FailedLead:
            async with semaphore:
                try:
                    return await self._seller_writer_port.enrich_and_create(
                        draft_from_lead(lead),
                        enrichment_timeout_s=max(deadline - loop.time(), 0.0),
                    )
                except SellerWriteError as exc:
                    logger.warning("discovery_seller_write_failed lead=%s error=%s", lead.name, exc)
                    return FailedLead(lead=lead, reason=str(exc), landed=exc.landed)
                except Exception:
                    logger.exception("discovery_seller_write_crashed", extra={"lead": lead.name})
                    return FailedLead(lead=lead, reason="unexpected error")

        results = await asyncio.gather(*(_create(lead) for lead in leads))
        created = tuple(r for r in results if isinstance(r, CreatedSeller))
        needs_review = tuple(r for r in results if isinstance(r, UnverifiedSeller))
        failed = tuple(r for r in results if isinstance(r, FailedLead))
        return created, needs_review, failed
