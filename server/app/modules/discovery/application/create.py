"""Search, pre-filter against the CRM, then auto-create what's new.

Replaces the human `/add-seller` step as the dedupe gate: an exact `place_id`
or domain hit skips a lead, as does a similar name, and only leads with no CRM
match are written. A lead whose enriched fields came from a provider whose
website disagrees with Maps' is skipped too. Skipped leads free their slot, so
the search keeps going until `lead_limit` sellers are written or the pool runs out.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.modules.discovery.application.base import ServiceBase
from app.modules.discovery.domain.crm import CrmMatchKind
from app.modules.discovery.domain.drafts import draft_from_lead
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.domain.outcome import (
    CreatedSeller,
    DiscoveryOutcome,
    FailedLead,
    SellerWriteError,
    UnverifiedSeller,
)

logger = logging.getLogger(__name__)

# One Places call returns up to 20 at the same price as 1, so search wide and
# let the CRM pre-filter, not the API, decide which few survive.
_CANDIDATE_POOL = 20
# An ignored review card stops hiding its lead after this, so it gets a fresh look.
_REVIEW_EXPIRY = timedelta(days=30)


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
        limit = self._policy.lead_limit
        loop = asyncio.get_running_loop()
        # One budget for every round, so refilling slots can't multiply the wait.
        deadline = loop.time() + self._policy.enrichment_budget_s
        created: list[CreatedSeller] = []
        failed: list[FailedLead] = []
        possible_duplicates = already_in_crm = awaiting_review = unverified_skipped = 0
        remaining = iter(leads)
        while len(created) < limit:
            # A lead that fails its website check or its write frees its slot, so
            # keep taking the next ones until `limit` sellers are written.
            batch: list[DiscoveredLead] = []
            for lead in remaining:
                match = await self._seller_writer_port.find_existing(lead)
                if match.kind in (CrmMatchKind.PLACE_ID, CrmMatchKind.DOMAIN):
                    already_in_crm += 1
                elif match.kind is CrmMatchKind.FUZZY_NAME:
                    possible_duplicates += 1
                elif lead.place_id in pending:
                    # Its earlier card still works; don't pay to enrich it again.
                    awaiting_review += 1
                else:
                    batch.append(lead)
                    if len(batch) >= limit - len(created):
                        break
            if not batch:
                break
            done, unverified, errors = await self._create_all(batch, deadline)
            created.extend(done)
            unverified_skipped += len(unverified)
            failed.extend(errors)

        return DiscoveryOutcome(
            status="ok",
            created=tuple(created),
            possible_duplicates=possible_duplicates,
            unverified_skipped=unverified_skipped,
            failed=tuple(failed),
            already_in_crm=already_in_crm,
            awaiting_review=awaiting_review,
        )

    async def _pending_reviews(self, leads: list[DiscoveredLead]) -> set[str]:
        """Fails open: a store outage re-posts a lead rather than hiding it."""
        try:
            return await self._review_store.pending_place_ids(
                [lead.place_id for lead in leads if lead.place_id],
                flagged_since=datetime.now(UTC) - _REVIEW_EXPIRY,
            )
        except Exception:
            logger.exception("discovery_pending_reviews_lookup_failed")
            return set()

    async def _create_all(
        self, leads: list[DiscoveredLead], deadline: float
    ) -> tuple[tuple[CreatedSeller, ...], tuple[UnverifiedSeller, ...], tuple[FailedLead, ...]]:
        semaphore = asyncio.Semaphore(self._policy.enrichment_concurrency)
        loop = asyncio.get_running_loop()

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
