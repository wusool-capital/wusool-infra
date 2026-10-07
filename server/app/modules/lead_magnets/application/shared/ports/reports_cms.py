"""The Webflow Reports collection seam. Faked in tests, implemented by
`providers/webflow/reports_cms.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_report.report import Pin, ReportDocument


class ReportsCmsPort(Protocol):
    async def find(self, slug: str) -> str | None:
        """The id of the card with this slug, published or not."""
        ...

    async def create(self, report: ReportDocument) -> str:
        """Creates the card already published to the live site and returns its id."""
        ...

    async def update(self, item_id: str, report: ReportDocument) -> None: ...

    async def unpublish(self, item_id: str) -> None: ...

    async def unpin(self, item_id: str, pins: tuple[Pin, ...]) -> None:
        """Clears `pins` on the live card only; the card is otherwise left as it is."""
        ...
