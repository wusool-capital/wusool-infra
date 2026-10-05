"""The Webflow Insights collection seam. Faked in tests, implemented by
`providers/webflow/insights_cms.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_report.report import CmsItem, ReportDocument


class InsightsCmsPort(Protocol):
    async def find(self, slug: str) -> CmsItem | None: ...

    async def create(self, report: ReportDocument, *, featured: bool | None) -> None:
        """Creates the card already published to the live site. `featured`
        `None` leaves the card's pin as it is."""
        ...

    async def update(
        self, item_id: str, report: ReportDocument, *, featured: bool | None
    ) -> None: ...

    async def unpublish(self, item_id: str) -> None: ...

    async def featured_ids(self) -> list[str]: ...

    async def unfeature(self, item_id: str) -> None: ...
