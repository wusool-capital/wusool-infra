"""LinkedIn scan of a role's contacts: profiles (for job changes) and recent
posts (the activity signal). Self-contained — nothing here depends on the
proposal — so a future watcher can call `scan_linkedin` on its own.
"""

import asyncio
import logging

from app.modules.enrichment.application.base import ServiceBase
from app.modules.enrichment.application.ports.linkedin import PostedLimit
from app.modules.enrichment.domain.linkedin import (
    JobChange,
    LinkedInScan,
    detect_job_change,
    profile_key,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget

logger = logging.getLogger(__name__)

_MAX_POSTS = 10
_POSTED_LIMIT: PostedLimit = "month"
_SCAN_TIMEOUT_S = 60


class LinkedInMixin(ServiceBase):
    async def scan_linkedin(self, target: EnrichmentTarget) -> LinkedInScan:
        """Empty when no LinkedIn client is configured. Never raises: a slow
        or failing vendor must not take the caller down with it."""
        if self._linkedin_client is None:
            return LinkedInScan()
        client = self._linkedin_client
        targets = await self._role_reader.load_linkedin_targets(target)

        contacts = [c for c in targets.contacts if c.linkedin_url]
        missing = tuple(c for c in targets.contacts if not c.linkedin_url)
        for contact in missing:
            logger.info("linkedin_contact_skipped_no_url person=%s", contact.person_attio_id)
        urls = tuple(c.linkedin_url for c in contacts if c.linkedin_url)
        if not urls:
            return LinkedInScan(contacts_without_linkedin=missing)

        post_urls = (*urls, targets.company_url) if targets.company_url else urls
        try:
            async with asyncio.timeout(_SCAN_TIMEOUT_S):
                profiles, posts = await asyncio.gather(
                    client.profiles(urls),
                    client.posts(post_urls, max_posts=_MAX_POSTS, posted_limit=_POSTED_LIMIT),
                )
        except Exception:
            logger.warning("linkedin_scan_failed role=%s", target.role_id, exc_info=True)
            return LinkedInScan(contacts_without_linkedin=missing)

        by_key = {profile_key(p.url): p for p in profiles}
        changes: list[JobChange] = []
        for contact in contacts:
            profile = by_key.get(profile_key(contact.linkedin_url))
            if profile and (change := detect_job_change(contact, profile)):
                changes.append(change)
        return LinkedInScan(
            job_changes=tuple(changes), posts=posts, contacts_without_linkedin=missing
        )
