"""The product-analytics seam. Faked in tests, implemented by
`providers/posthog/client.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_report.report_event import ReportEvent


class AnalyticsPort(Protocol):
    async def capture(self, event: ReportEvent) -> None:
        """Queues the event. Never raises: analytics must not fail a reader."""
        ...

    async def shutdown(self) -> None:
        """Sends whatever is still queued."""
        ...
