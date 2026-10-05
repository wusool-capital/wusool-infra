"""Keeps the Webflow Insights card in step with a report published in Sanity.

Triggered by Sanity's publish webhook. Every call re-reads the report rather
than trusting the webhook body, so a retried or out-of-order delivery still
lands the current state.

It also flattens the pasted HTML once per version: some exports draw their
pages with JavaScript, and a gate can only split what is already on the page.
"""

import logging

from app.modules.lead_magnets.application.shared.ports import (
    InsightsCmsPort,
    ReportRendererPort,
    ReportSourcePort,
)
from app.modules.lead_magnets.domain.insights_report.report import fingerprint

logger = logging.getLogger(__name__)


class ReportSync:
    def __init__(
        self, *, source: ReportSourcePort, cms: InsightsCmsPort, renderer: ReportRendererPort
    ) -> None:
        self._source = source
        self._cms = cms
        self._renderer = renderer

    async def sync(
        self, *, slug: str | None, previous_slug: str | None, featured_changed: bool = False
    ) -> None:
        """`slug` is `None` when the report was deleted or unpublished;
        `previous_slug` differs from it when an editor renamed the slug.

        The pin only moves when this edit ticked or unticked it. Pinning a
        newer report unpins the older card in Webflow only, so the older
        report still says "pinned" in Sanity; acting on that on every edit
        would steal the pin back on a typo fix."""
        if previous_slug and previous_slug != slug:
            await self._source.refresh(previous_slug)
            await self._unpublish(previous_slug)
        if slug is None:
            return

        source = await self._source.source(slug)
        if source is not None and source.rendered_from != (version := fingerprint(source.html)):
            rendered = await self._renderer.render(source.html)
            await self._source.save_rendered(source.document_id, rendered, version)

        report = await self._source.refresh(slug)
        if report is None:
            await self._unpublish(slug)
            return

        item = await self._cms.find(slug)
        if item is not None and not item.gated:
            # Hand-written articles are never gated; a clashing slug must not overwrite one.
            logger.warning("insights_report_sync_skipped_ungated slug=%s", slug)
            return

        featured = report.featured if featured_changed else None
        if featured:
            # One pinned card only; this is the sync's single write to articles it didn't create.
            for item_id in await self._cms.featured_ids():
                if item is None or item_id != item.id:
                    await self._cms.unfeature(item_id)

        if item is None:
            await self._cms.create(report, featured=featured)
        else:
            await self._cms.update(item.id, report, featured=featured)

    async def _unpublish(self, slug: str) -> None:
        item = await self._cms.find(slug)
        if item is not None and item.gated:
            await self._cms.unpublish(item.id)
