"""The report CMS seam. Faked in tests, implemented by
`providers/sanity/report_source.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_report.report import (
    LostPins,
    Pin,
    ReportDocument,
    ReportSource,
)


class ReportSourcePort(Protocol):
    async def get(self, slug: str) -> ReportDocument | None:
        """The published report, or `None` when it doesn't exist or isn't
        published. May be a few minutes stale."""
        ...

    async def refresh(self, slug: str) -> ReportDocument | None:
        """Like `get`, but never stale, and replaces the cached copy."""
        ...

    async def source(self, slug: str) -> ReportSource | None:
        """The pasted HTML, never stale. `None` when not published."""
        ...

    async def save_rendered(
        self, source: ReportSource, *, html: str, preview_end: int, rendered_from: str
    ) -> bool:
        """Stores the flattened HTML that `get` serves from then on. `False`
        when the document changed since `source` was read; nothing is saved."""
        ...

    async def unpin_others(
        self, pins: list[Pin], document_id: str, *, pinned_at: str | None
    ) -> list[LostPins]:
        """Unticks `pins` on every other report, drafts included, last edited no
        later than `pinned_at`, in one transaction, and returns what each lost.
        The time check lets the later of two near-simultaneous pins win."""
        ...
