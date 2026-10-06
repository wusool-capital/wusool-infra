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
from app.modules.lead_magnets.domain.insights_report.split import split_report

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
        would steal the pin back on a typo fix. When nothing is left pinned,
        the newest live card takes the slot."""
        if previous_slug and previous_slug != slug:
            await self._source.refresh(previous_slug)
            await self._unpublish(previous_slug)
        if slug is None:
            await self._keep_one_pinned()
            return

        source = await self._source.source(slug)
        if source is not None and source.rendered_from != (version := fingerprint(source.html)):
            rendered = await self._renderer.render(source.html)
            preview, _ = split_report(rendered)
            saved = await self._source.save_rendered(
                source, html=rendered, preview_end=len(preview), rendered_from=version
            )
            if not saved:
                # Edited again mid-render; that edit's own webhook syncs the newer version.
                logger.info("insights_report_sync_superseded slug=%s", slug)
                return

        report = await self._source.refresh(slug)
        if report is None:
            await self._unpublish(slug)
            await self._keep_one_pinned()
            return

        item = await self._cms.find(slug)
        if item is not None and not item.gated:
            # Hand-written articles are never gated; a clashing slug must not overwrite one.
            logger.warning("insights_report_sync_skipped_ungated slug=%s", slug)
            return

        featured = report.featured if featured_changed else None
        if item is None:
            card_id = await self._cms.create(report, featured=featured)
        else:
            card_id = item.id
            await self._cms.update(card_id, report, featured=featured)

        if featured:
            # Unpinned only once this card is live, so a failed write never empties the slot.
            for item_id in await self._cms.featured_ids():
                if item_id != card_id:
                    await self._cms.unfeature(item_id)
        else:
            # An unticked card must not win the fallback straight back.
            await self._keep_one_pinned(excluding=card_id if featured is False else None)

    async def _unpublish(self, slug: str) -> None:
        item = await self._cms.find(slug)
        if item is not None and item.gated:
            await self._cms.unpublish(item.id)

    async def _keep_one_pinned(self, *, excluding: str | None = None) -> None:
        """The featured block lists every pinned card; with none it reads "No items found".
        This and the unpins are the sync's only writes to articles it didn't create."""
        # `excluding` may still read as pinned while its unpin publishes.
        if any(item_id != excluding for item_id in await self._cms.featured_ids()):
            return
        if newest := await self._cms.newest_id(excluding=excluding):
            await self._cms.feature(newest)
