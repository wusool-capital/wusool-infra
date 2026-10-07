"""The Webflow Reports collection seam. Faked in tests, implemented by
`providers/webflow/reports_cms.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_report.report import ReportDocument


class ReportsCmsPort(Protocol):
    async def find(self, slug: str) -> str | None:
        """The id of the card with this slug, published or not."""
        ...

    async def create(self, report: ReportDocument, *, featured: bool | None) -> str:
        """Creates the card already published to the live site and returns its
        id. `featured` `None` leaves the card's pin as it is."""
        ...

    async def update(
        self, item_id: str, report: ReportDocument, *, featured: bool | None
    ) -> None: ...

    async def unpublish(self, item_id: str) -> None: ...

    async def featured_ids(self) -> list[str]: ...

    async def newest_id(self, *, excluding: str | None = None) -> str | None:
        """The live card with the latest published date, skipping `excluding`."""
        ...

    async def feature(self, item_id: str) -> None: ...

    async def unfeature(self, item_id: str) -> None: ...
