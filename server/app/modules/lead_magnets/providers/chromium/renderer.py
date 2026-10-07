"""Chromium implementation of `ReportRendererPort`. `render` runs once per
published report version, never per reader; `pdf` runs per download.

Some report exports are self-unpacking bundles: the page exists only after
their JavaScript runs (the first playbook drew 40 A4 pages and React tables
that way). This opens the HTML in headless Chromium, waits for the page to
stop changing, and saves what was drawn as plain HTML: no scripts, images
inlined, and shadow-DOM page styles copied inline, since shadow DOM doesn't
serialize. Plain HTML passes through essentially unchanged.

Nothing in it may reach the network from inside our VPC: HTTP is aborted by
`page.route`, WebSockets by `page.route_web_socket`, and as a backstop every
connection goes to a dead proxy and WebRTC may not send unproxied UDP.
Bundles carry their assets inline; external stylesheets stay as `<link>`
tags for the reader's browser to load.

A render is capped at `_RENDER_TIMEOUT_S` overall, and the "wait until the
page stops changing" step at `_SETTLE_MAX_MS`, so an animated page is saved
as it stands rather than holding the render lock forever.
"""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import Page, Route, WebSocketRoute, async_playwright

_QUIET_MS = 1500
_SETTLE_MAX_MS = 8_000
_TIMEOUT_MS = 20_000
_RENDER_TIMEOUT_S = 30
_ISOLATED = [
    "--proxy-server=127.0.0.1:9",
    "--proxy-bypass-list=<-loopback>",
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
]

# A refresh navigates mid-render and destroys the page being saved; it never belongs in a report.
_META_REFRESH = re.compile(r"<meta\b[^>]*http-equiv\s*=\s*[\"']?refresh[^>]*>", re.IGNORECASE)

_HERE = Path(__file__).parent
_WAIT_FOR_QUIET = (_HERE / "wait_for_quiet.js").read_text()
_SERIALIZE = (_HERE / "serialize.js").read_text()


async def _block(route: Route) -> None:
    await route.abort()


async def _block_socket(socket: WebSocketRoute) -> None:
    await socket.close()


class ChromiumReportRenderer:
    def __init__(self) -> None:
        # ponytail: one Chromium at a time, PDF downloads included (~300 MB peak, 2 GB t3.small).
        # Cache PDFs per version if downloads start queueing.
        self._lock = asyncio.Lock()

    async def render(self, html: str) -> str:
        async with self._lock:
            return await asyncio.wait_for(self._render(html), _RENDER_TIMEOUT_S)

    async def pdf(self, html: str) -> bytes:
        async def locked() -> bytes:
            async with self._lock:
                return await self._pdf(html)

        # The queue counts toward the cap, so downloads fail fast rather than pile up.
        return await asyncio.wait_for(locked(), _RENDER_TIMEOUT_S)

    async def _render(self, html: str) -> str:
        async with _isolated_page() as page:
            await page.set_content(_META_REFRESH.sub("", html), wait_until="load")
            settle = {"quietMs": _QUIET_MS, "maxMs": _SETTLE_MAX_MS}
            await page.evaluate(_WAIT_FOR_QUIET, settle)
            await page.evaluate("document.fonts.ready.then(() => true)")
            return await page.evaluate(_SERIALIZE)

    async def _pdf(self, html: str) -> bytes:
        # Flattened HTML has no scripts, so nothing to wait for beyond load and fonts.
        async with _isolated_page() as page:
            await page.set_content(html, wait_until="load")
            await page.evaluate("document.fonts.ready.then(() => true)")
            return await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                prefer_css_page_size=True,
            )


@asynccontextmanager
async def _isolated_page() -> AsyncIterator[Page]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=_ISOLATED)
        try:
            page = await browser.new_page(viewport={"width": 1200, "height": 900})
            page.set_default_timeout(_TIMEOUT_MS)
            await page.route("**/*", _block)
            await page.route_web_socket("**/*", _block_socket)
            yield page
        finally:
            await browser.close()
