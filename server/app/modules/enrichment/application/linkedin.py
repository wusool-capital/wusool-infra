"""LinkedIn scan of a role's company page: its recent posts (the activity
signal). Self-contained — nothing here depends on the proposal — so a future
watcher can call `scan_linkedin` on its own.

The people path (a role's contacts: profiles for job changes, and their own
posts) is built and tested but off: `include_people` defaults to False and no
caller sets it yet.
"""

import asyncio
import logging

from app.modules.enrichment.application.base import ServiceBase
from app.modules.enrichment.application.ports.linkedin import PostedLimit
from app.modules.enrichment.domain.linkedin import (
    Contact,
    JobChange,
    LinkedInProfile,
    LinkedInScan,
    ScanOutcome,
    detect_job_change,
    profile_key,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget

logger = logging.getLogger(__name__)

_MAX_POSTS = 10
_POSTED_LIMIT: PostedLimit = "month"
_SCAN_TIMEOUT_S = 60


async def _no_profiles() -> tuple[LinkedInProfile, ...]:
    return ()


class LinkedInMixin(ServiceBase):
    async def scan_linkedin(
        self,
        target: EnrichmentTarget,
        *,
        include_people: bool = False,
        requested_by: str | None = None,
    ) -> LinkedInScan:
        """Only what is new since the last scan once history is configured,
        everything otherwise. `outcome` says why a scan has no results:
        `SKIPPED` (no client, or no LinkedIn page saved) or `FAILED`. Never
        raises: a slow or failing vendor must not take the caller down.
        `requested_by` is the Slack user who triggered the scan, recorded as
        the activity's actor."""
        if self._linkedin_client is None:
            return LinkedInScan(outcome=ScanOutcome.SKIPPED)
        client = self._linkedin_client
        contacts: list[Contact] = []
        missing: tuple[Contact, ...] = ()
        try:
            targets = await self._role_reader.load_linkedin_targets(
                target, include_contacts=include_people
            )
            contacts = [c for c in targets.contacts if c.linkedin_url]
            missing = tuple(c for c in targets.contacts if not c.linkedin_url)
            for contact in missing:
                logger.info("linkedin_contact_skipped_no_url person=%s", contact.person_attio_id)
            profile_urls = tuple(c.linkedin_url for c in contacts if c.linkedin_url)
            post_urls = (
                (*profile_urls, targets.company_url) if targets.company_url else profile_urls
            )
            if not post_urls:
                logger.info("linkedin_scan_skipped_no_urls role=%s", target.role_id)
                return LinkedInScan(contacts_without_linkedin=missing, outcome=ScanOutcome.SKIPPED)

            async with asyncio.timeout(_SCAN_TIMEOUT_S):
                profiles, posts = await asyncio.gather(
                    client.profiles(profile_urls) if profile_urls else _no_profiles(),
                    client.posts(post_urls, max_posts=_MAX_POSTS, posted_limit=_POSTED_LIMIT),
                )
        except Exception as exc:
            logger.warning("linkedin_scan_failed role=%s", target.role_id, exc_info=True)
            failed = LinkedInScan(contacts_without_linkedin=missing, outcome=ScanOutcome.FAILED)
            await self._record_failure(target, failed, requested_by, type(exc).__name__)
            return failed

        by_key = {profile_key(p.url): p for p in profiles}
        changes: list[JobChange] = []
        for contact in contacts:
            profile = by_key.get(profile_key(contact.linkedin_url))
            if profile and (change := detect_job_change(contact, profile)):
                changes.append(change)
        scan = LinkedInScan(
            job_changes=tuple(changes),
            posts=posts,
            contacts_without_linkedin=missing,
            contacts_scanned=len(contacts),
        )
        if self._linkedin_history is None:
            return scan
        try:
            return await self._linkedin_history.record(target, scan, requested_by=requested_by)
        except Exception:
            # Showing a repeat is better than showing nothing.
            logger.warning("linkedin_history_failed role=%s", target.role_id, exc_info=True)
            return scan

    async def _record_failure(
        self,
        target: EnrichmentTarget,
        scan: LinkedInScan,
        requested_by: str | None,
        failure: str,
    ) -> None:
        if self._linkedin_history is None:
            return
        try:
            await self._linkedin_history.record(
                target, scan, requested_by=requested_by, failure=failure
            )
        except Exception:
            logger.warning("linkedin_history_failed role=%s", target.role_id, exc_info=True)
