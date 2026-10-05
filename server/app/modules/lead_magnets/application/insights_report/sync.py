"""Keeps the Webflow Insights card in step with a report published in Sanity.

Triggered by Sanity's publish webhook. Every call re-reads the report rather
than trusting the webhook body, so a retried or out-of-order delivery still
lands the current state.
"""

import logging

from app.modules.lead_magnets.application.shared.ports import InsightsCmsPort, ReportSourcePort

logger = logging.getLogger(__name__)


class ReportSync:
    def __init__(self, *, source: ReportSourcePort, cms: InsightsCmsPort) -> None:
        self._source = source
        self._cms = cms

    async def sync(self, *, slug: str | None, previous_slug: str | None) -> None:
        """`slug` is `None` when the report was deleted or unpublished;
        `previous_slug` differs from it when an editor renamed the slug."""
        if previous_slug and previous_slug != slug:
            await self._source.refresh(previous_slug)
            await self._unpublish(previous_slug)
        if slug is None:
            return

        report = await self._source.refresh(slug)
        if report is None:
            await self._unpublish(slug)
            return

        item = await self._cms.find(slug)
        if item is not None and not item.gated:
            # Hand-written articles are never gated; a clashing slug must not overwrite one.
            logger.warning("insights_report_sync_skipped_ungated slug=%s", slug)
            return

        if report.featured:
            # One pinned card only; this is the sync's single write to articles it didn't create.
            for item_id in await self._cms.featured_ids():
                if item is None or item_id != item.id:
                    await self._cms.unfeature(item_id)

        if item is None:
            await self._cms.create(report)
        else:
            await self._cms.update(item.id, report)

    async def _unpublish(self, slug: str) -> None:
        item = await self._cms.find(slug)
        if item is not None and item.gated:
            await self._cms.unpublish(item.id)
