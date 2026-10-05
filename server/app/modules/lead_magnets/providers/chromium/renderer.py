"""Chromium implementation of `ReportRendererPort`, run once per published
report version, never per reader.

Some report exports are self-unpacking bundles: the page exists only after
their JavaScript runs (the first playbook drew 40 A4 pages and React tables
that way). This opens the HTML in headless Chromium, waits for the page to
stop changing, and saves what was drawn as plain HTML: no scripts, images
inlined, and shadow-DOM page styles copied inline, since shadow DOM doesn't
serialize. Plain HTML passes through essentially unchanged.

Every network request is blocked. The HTML is staff content, but nothing in
it should reach the network from inside our VPC. Bundles carry their assets
inline, and external stylesheets stay as `<link>` tags for the reader's
browser to load.
"""

import asyncio
from pathlib import Path

from playwright.async_api import Route, async_playwright

_QUIET_MS = 1500
_TIMEOUT_MS = 30_000

_HERE = Path(__file__).parent
_WAIT_FOR_QUIET = (_HERE / "wait_for_quiet.js").read_text()
_SERIALIZE = (_HERE / "serialize.js").read_text()


async def _block(route: Route) -> None:
    await route.abort()


class ChromiumReportRenderer:
    def __init__(self) -> None:
        # ponytail: one render at a time; Chromium peaks around 300 MB on a 2 GB t3.small.
        self._lock = asyncio.Lock()

    async def render(self, html: str) -> str:
        async with self._lock, async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page(viewport={"width": 1200, "height": 900})
                page.set_default_timeout(_TIMEOUT_MS)
                await page.route("**/*", _block)
                await page.set_content(html, wait_until="load")
                await page.evaluate(_WAIT_FOR_QUIET, _QUIET_MS)
                await page.evaluate("document.fonts.ready.then(() => true)")
                return await page.evaluate(_SERIALIZE)
            finally:
                await browser.close()
