"""`ChromiumReportRenderer` against a miniature of the design-tool export
that motivated it. Needs the Chromium build Playwright installs (the
Dockerfile does); skipped where it isn't there.
"""

import asyncio
import functools
import os
import re

import httpx
import pytest
from playwright.async_api import async_playwright

from app.modules.lead_magnets.domain.insights_report.split import split_report
from app.modules.lead_magnets.providers.chromium.renderer import ChromiumReportRenderer

_EXPORT = """<!DOCTYPE html><html><head>
<style>doc-page:not(:defined){visibility:hidden} p{color:#000523}</style>
<style>@page{size:A4;margin:0} body{margin:0}</style>
</head><body>
<x-dc><section>SOURCE TEMPLATE WITH EVERY PAGE</section></x-dc>
<doc-page><section class="page">static page one</section></doc-page>
<img src="http://169.254.169.254/latest/meta-data" style="position:absolute;top:0">
<script>
  customElements.define('doc-page', class extends HTMLElement {
    constructor() { super(); this.attachShadow({mode: 'open'}).innerHTML =
      '<style>:host{display:block;padding:48px 24px;background:#f5f5f4}' +
      '::slotted(.page){width:794px;height:296mm;overflow:hidden;' +
      'box-shadow:0 2px 10px rgba(0,0,0,.25);border-radius:7px}' +
      '::slotted(.page:not(:first-child)){margin-top:16px}</style><slot></slot>'; }
  });
  document.querySelector('doc-page').insertAdjacentHTML('beforeend',
    '<section class="page">page two drawn by script</section>');
</script>
</body></html>"""


async def _require_chromium() -> None:
    """Skips locally without a browser; fails in CI, where the workflow installs one."""
    if await _chromium_available():
        return
    if os.environ.get("CI"):
        pytest.fail("Chromium missing in CI: the renderer's security tests would not run")
    pytest.skip("Chromium is not installed (run `playwright install --only-shell chromium`)")


async def _chromium_available() -> bool:
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            await browser.close()
        return True
    except Exception:  # noqa: BLE001 - any launch failure means "not installed here"
        return False


async def test_a_script_built_export_becomes_static_html() -> None:
    await _require_chromium()

    html = await ChromiumReportRenderer().render(_EXPORT)

    assert "page two drawn by script" in html
    assert "<script" not in html
    assert "SOURCE TEMPLATE WITH EVERY PAGE" not in html, "the hidden source would leak"
    assert ":not(:defined)" not in html, "it would hide the page once scripts are gone"
    assert "width: 794px" in html, "the shadow-DOM page width is copied inline"


async def test_pages_keep_the_viewers_gaps_on_screen_but_print_one_per_sheet() -> None:
    await _require_chromium()
    renderer = ChromiumReportRenderer()

    html = await renderer.render(_EXPORT)
    pdf = await renderer.pdf(html)

    assert "background-color:rgb(245, 245, 244);padding:48px 24px" in html, "the desk shows"
    assert "border-radius:7px" in html and "margin-top:16px" in html
    assert len(re.findall(rb"/Type\s*/Page\b(?!s)", pdf)) == 2, "a gap would spill onto a sheet"


async def test_the_preview_is_exactly_the_first_page() -> None:
    await _require_chromium()

    html = await ChromiumReportRenderer().render(_EXPORT)
    preview, rest = split_report(html)

    assert html.count("data-wusool-gate") == 1
    assert "static page one" in preview and "page two" not in preview
    assert "page two drawn by script" in rest


async def test_without_pages_the_gate_falls_after_the_first_block() -> None:
    await _require_chromium()
    paragraphs = "".join(f'<p style="height:100px;margin:0">p{n}</p>' for n in range(20))

    html = await ChromiumReportRenderer().render(f"<body style='margin:0'>{paragraphs}</body>")
    preview, _ = split_report(html)

    assert html.count("data-wusool-gate") == 1
    assert preview.count("<p") == 1


async def test_no_way_to_run_code_or_frame_third_parties_survives() -> None:
    """Report HTML is served on the tools origin, so nothing executable may remain."""
    await _require_chromium()
    html = (
        '<body><p>kept</p><img src="x" onerror="alert(1)"><a href=" javascript:alert(2)">a</a>'
        '<div onclick="alert(3)">d</div><iframe src="https://evil.example"></iframe>'
        '<object data="x"></object><embed src="x"><base href="https://evil.example/">'
        '<meta http-equiv="refresh" content="0;url=https://evil.example">'
        '<img src="data:image/png;base64,iVBORw0KGgo="></body>'
    )

    out = await ChromiumReportRenderer().render(html)

    for vector in (
        "onerror",
        "onclick",
        "javascript:",
        "<iframe",
        "<object",
        "<embed",
        "<base",
        "http-equiv",
    ):
        assert vector not in out, vector
    assert "kept" in out
    assert "data:image/png" in out, "inlined images must survive"


async def test_rendering_cannot_reach_the_network() -> None:
    """Pasted HTML runs inside our VPC; HTTP, images and WebSockets must all fail."""
    await _require_chromium()
    hits: list[int] = []

    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        hits.append(1)
        writer.close()

    server = await asyncio.start_server(on_connect, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    probe = (
        f"<body><p>x</p><script>new WebSocket('ws://127.0.0.1:{port}/');"
        f"fetch('http://127.0.0.1:{port}/').catch(() => {{}});"
        f"new Image().src = 'http://127.0.0.1:{port}/i.png';</script></body>"
    )
    try:
        await ChromiumReportRenderer().render(probe)
    finally:
        server.close()

    assert hits == []


async def test_the_pdf_keeps_the_reports_own_page_size_and_stays_offline() -> None:
    """Flattened reports carry their own A4 pages; printing must not reflow them or fetch."""
    await _require_chromium()
    hits: list[int] = []

    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        hits.append(1)
        writer.close()

    server = await asyncio.start_server(on_connect, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    page = '<section style="height:297mm;overflow:hidden;break-after:page">p</section>'
    html = (
        f"<style>@page{{size:A4;margin:0}} body{{margin:0}}</style>"
        f'<img src="http://127.0.0.1:{port}/i.png" style="position:absolute">{page * 3}'
    )
    try:
        pdf = await ChromiumReportRenderer().pdf(html)
    finally:
        server.close()

    assert pdf.startswith(b"%PDF-")
    assert len(re.findall(rb"/Type\s*/Page\b(?!s)", pdf)) == 3
    assert hits == []


async def test_the_pdf_loads_google_fonts_but_no_other_linked_asset(monkeypatch) -> None:
    """Fetched by Python from a fixed allow-list, so Chromium still reaches nothing itself."""
    await _require_chromium()
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        fetched.append(str(request.url))
        return httpx.Response(200, text="body{margin:0}", headers={"content-type": "text/css"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        functools.partial(real_client, transport=httpx.MockTransport(handler)),
    )
    html = (
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">'
        '<link rel="stylesheet" href="https://evil.example/x.css"><p>x</p>'
    )

    pdf = await ChromiumReportRenderer().pdf(html)

    assert pdf.startswith(b"%PDF-")
    assert fetched == ["https://fonts.googleapis.com/css2?family=Inter"]


async def test_a_rich_reports_own_gate_survives_rendering() -> None:
    """The serializer places a gate only when the page arrives without one."""
    await _require_chromium()
    page = "<body><p>one</p><p>two</p><div data-wusool-gate></div><p>three</p></body>"

    preview, _ = split_report(await ChromiumReportRenderer().render(page))

    assert "two" in preview and "three" not in preview
