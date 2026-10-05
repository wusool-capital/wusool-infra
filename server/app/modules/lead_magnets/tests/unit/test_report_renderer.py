"""`ChromiumReportRenderer` against a miniature of the design-tool export
that motivated it. Needs the Chromium build Playwright installs (the
Dockerfile does); skipped where it isn't there.
"""

import pytest
from playwright.async_api import async_playwright

from app.modules.lead_magnets.domain.insights_report.split import split_report
from app.modules.lead_magnets.providers.chromium.renderer import ChromiumReportRenderer

_EXPORT = """<!DOCTYPE html><html><head>
<style>doc-page:not(:defined){visibility:hidden} p{color:#000523}</style>
</head><body>
<x-dc><section>SOURCE TEMPLATE WITH EVERY PAGE</section></x-dc>
<doc-page><section class="page">static page one</section></doc-page>
<img src="http://169.254.169.254/latest/meta-data">
<script>
  customElements.define('doc-page', class extends HTMLElement {
    constructor() { super(); this.attachShadow({mode: 'open'}).innerHTML =
      '<style>::slotted(.page){width:794px}</style><slot></slot>'; }
  });
  document.querySelector('doc-page').insertAdjacentHTML('beforeend',
    '<section class="page">page two drawn by script</section>');
</script>
</body></html>"""


async def _chromium_available() -> bool:
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            await browser.close()
        return True
    except Exception:  # noqa: BLE001 - any launch failure means "not installed here"
        return False


async def test_a_script_built_export_becomes_static_html() -> None:
    if not await _chromium_available():
        pytest.skip("Chromium is not installed (run `playwright install --only-shell chromium`)")

    html = await ChromiumReportRenderer().render(_EXPORT)

    assert "page two drawn by script" in html
    assert "<script" not in html
    assert "SOURCE TEMPLATE WITH EVERY PAGE" not in html, "the hidden source would leak"
    assert ":not(:defined)" not in html, "it would hide the page once scripts are gone"
    assert "width: 794px" in html, "the shadow-DOM page width is copied inline"


async def test_the_gate_is_marked_at_a_quarter_of_the_drawn_height() -> None:
    if not await _chromium_available():
        pytest.skip("Chromium is not installed (run `playwright install --only-shell chromium`)")
    paragraphs = "".join(f'<p style="height:100px;margin:0">p{n}</p>' for n in range(20))

    html = await ChromiumReportRenderer().render(f"<body style='margin:0'>{paragraphs}</body>")
    preview, _ = split_report(html)

    assert html.count("data-wusool-gate") == 1
    assert preview.count("<p") == 5, "25% of 20 equal-height blocks"
