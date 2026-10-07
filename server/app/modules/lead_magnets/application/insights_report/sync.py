"""Keeps the Webflow Reports card in step with a report published in Sanity.

Triggered by Sanity's publish webhook. Every call re-reads the report rather
than trusting the webhook body, so a retried or out-of-order delivery still
lands the current state.

It also flattens the pasted HTML once per version: some exports draw their
pages with JavaScript, and a gate can only split what is already on the page.
"""

import logging

from app.modules.lead_magnets.application.shared.ports import (
    ReportRendererPort,
    ReportsCmsPort,
    ReportSourcePort,
)
from app.modules.lead_magnets.domain.insights_report.report import fingerprint
from app.modules.lead_magnets.domain.insights_report.split import split_report

logger = logging.getLogger(__name__)


class ReportSync:
    def __init__(
        self, *, source: ReportSourcePort, cms: ReportsCmsPort, renderer: ReportRendererPort
    ) -> None:
        self._source = source
        self._cms = cms
        self._renderer = renderer

    async def sync(self, *, slug: str | None, previous_slug: str | None) -> None:
        """`slug` is `None` when the report was deleted or unpublished;
        `previous_slug` differs from it when an editor renamed the slug.

        Pins are level-triggered: every sync writes the report's own ticks, and
        taking a pin unticks it on the other reports in Sanity and Webflow, so
        the two always agree. With no pin, the /reports featured block falls
        back to the newest card by its own sort, and the home banner hides."""
        if previous_slug and previous_slug != slug:
            await self._source.refresh(previous_slug)
            await self._unpublish(previous_slug)
        if slug is None:
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
            return

        card_id = await self._cms.find(slug)
        if card_id is None:
            await self._cms.create(report)
        else:
            await self._cms.update(card_id, report)

        # After this card is live, so a failed write never empties a pin.
        for pin in report.pins:
            for other in await self._source.unpin_others(pin, slug, pinned_at=report.updated_at):
                if other_id := await self._cms.find(other):
                    await self._cms.unpin(other_id, pin)

    async def _unpublish(self, slug: str) -> None:
        if card_id := await self._cms.find(slug):
            await self._cms.unpublish(card_id)
