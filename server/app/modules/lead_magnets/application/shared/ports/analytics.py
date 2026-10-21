"""The product-analytics seam. Faked in tests, implemented by
`providers/posthog/client.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_report.report_event import ReportEvent
from app.modules.lead_magnets.domain.shared.lead_event import ConsentEvent, LeadEvent


class AnalyticsPort(Protocol):
    async def capture(self, event: ReportEvent) -> None:
        """Queues the event. Never raises: analytics must not fail a reader."""
        ...

    async def capture_lead(self, event: LeadEvent) -> None:
        """Queues a lead event, with the same never-raise rule."""
        ...

    async def capture_consent(self, event: ConsentEvent) -> None:
        """Counts a banner choice anonymously, with the same never-raise rule."""
        ...

    async def shutdown(self) -> None:
        """Sends whatever is still queued."""
        ...
