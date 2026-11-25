"""The plain-HTTPS page fetch seam. Faked in tests, implemented by
`providers/web/page_fetcher.py`."""

from typing import Protocol


class PageFetcherPort(Protocol):
    async def fetch_html(self, url: str) -> str:
        """The page's HTML, or `""` if it was blocked, slow, too large or failed."""
        ...
