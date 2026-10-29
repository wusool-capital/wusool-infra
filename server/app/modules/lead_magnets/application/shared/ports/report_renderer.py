"""The report flattening seam. Faked in tests, implemented by
`providers/chromium/renderer.py`."""

from typing import Protocol


class ReportRendererPort(Protocol):
    async def render(self, html: str, *, free_pages: int = 1) -> str:
        """The page as a browser draws it, saved as static HTML with no scripts.
        Without a gate of its own, it is gated after `free_pages` pages."""
        ...

    async def exhibit_images(self, html: str, exhibit_ids: tuple[str, ...]) -> dict[str, bytes]:
        """A PNG of each chart, by id (`<section id>#<figure index>`), as the bundle draws it.
        Raises when a chart isn't there."""
        ...

    async def pdf(self, html: str) -> bytes:
        """Already-flattened HTML printed to A4, honouring the report's own page size."""
        ...
