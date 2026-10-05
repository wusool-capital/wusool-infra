"""The report CMS seam. Faked in tests, implemented by
`providers/sanity/report_source.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_report.report import ReportDocument


class ReportSourcePort(Protocol):
    async def get(self, slug: str) -> ReportDocument | None:
        """The published report, or `None` when it doesn't exist or isn't
        published. May be a few minutes stale."""
        ...

    async def refresh(self, slug: str) -> ReportDocument | None:
        """Like `get`, but never stale, and replaces the cached copy."""
        ...
