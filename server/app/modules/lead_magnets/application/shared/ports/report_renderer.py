"""The report flattening seam. Faked in tests, implemented by
`providers/chromium/renderer.py`."""

from typing import Protocol


class ReportRendererPort(Protocol):
    async def render(self, html: str) -> str:
        """The page as a browser draws it, saved as static HTML with no scripts."""
        ...
