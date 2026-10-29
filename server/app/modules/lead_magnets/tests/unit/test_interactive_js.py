"""`shared/interactive.js` in a real browser, against a miniature bundle that swaps its page
in after load, as the design-tool exports do. Skipped where Chromium isn't installed.
"""

import asyncio

from playwright.async_api import async_playwright

from app.modules.lead_magnets.api.static import static_dir
from app.modules.lead_magnets.tests.unit.test_report_renderer import _require_chromium

_BUNDLE = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div id="root"></div><script>
  setTimeout(() => {
    document.getElementById('root').innerHTML =
      '<main style="padding:40px"><section id="beat-1"><p>NOT THIS ONE</p>' +
      '<figure><div id="chart" style="height:120px">THE CHART</div><p>caption</p></figure>' +
      '</section><section id="beat-2"><p>OTHER SECTION</p></section></main>';
  }, 150);
</script></body></html>"""
_PAGE = '<!doctype html><body><div id="host"></div></body>'


async def test_a_chart_is_shown_alone_with_its_own_content_and_its_height_reported() -> None:
    await _require_chromium()
    loader = (static_dir() / "shared" / "interactive.js").read_text(encoding="utf-8")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.route(
            "http://test.local/page", lambda r: r.fulfill(content_type="text/html", body=_PAGE)
        )
        await page.route(
            "http://test.local/bundle.html",
            lambda r: r.fulfill(
                content_type="text/html", body=_BUNDLE, headers={"access-control-allow-origin": "*"}
            ),
        )
        await page.goto("http://test.local/page")
        await page.add_script_tag(content=loader)
        await page.evaluate(
            """() => WusoolInteractive
              .mount(document.getElementById('host'), 'http://test.local/bundle.html', 'beat-1#0')
              .then((f) => new Promise((resolve) => f.addEventListener('ready', resolve)))"""
        )
        await asyncio.sleep(0.6)
        frame = next(f for f in page.frames if f != page.main_frame)
        shown = await frame.evaluate(
            """() => ({
              chart: document.getElementById('chart').getBoundingClientRect().height,
              caption: document.querySelector('figure p').getBoundingClientRect().height > 0,
              sibling: getComputedStyle(document.querySelector('#beat-1 > p')).display,
              other: getComputedStyle(document.getElementById('beat-2')).display,
              compat: document.compatMode,
              cookie: (() => {
                try { document.cookie; return 'readable' } catch (e) { return 'blocked' }
              })(),
            })"""
        )
        frame_height = await page.evaluate("document.querySelector('iframe').offsetHeight")
        await browser.close()

    assert shown["chart"] == 120 and shown["caption"], "the chart's own content must stay visible"
    assert shown["sibling"] == "none" and shown["other"] == "none"
    assert shown["compat"] == "CSS1Compat", "the script went ahead of the doctype"
    assert shown["cookie"] == "blocked", "the frame must not share the page's origin"
    assert 120 < frame_height < 220, "the frame follows the chart, not its starting height"


async def test_a_chart_that_never_draws_leaves_no_gap_in_the_page() -> None:
    await _require_chromium()
    loader = (static_dir() / "shared" / "interactive.js").read_text(encoding="utf-8")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.route(
            "http://test.local/page", lambda r: r.fulfill(content_type="text/html", body=_PAGE)
        )
        await page.route(
            "http://test.local/bundle.html",
            lambda r: r.fulfill(
                content_type="text/html", body=_BUNDLE, headers={"access-control-allow-origin": "*"}
            ),
        )
        await page.goto("http://test.local/page")
        await page.add_script_tag(content=loader)
        # `beat-9` is not in the bundle, so the frame can never report a height.
        await page.evaluate(
            "() => WusoolInteractive.mount(document.getElementById('host'), "
            "'http://test.local/bundle.html', 'beat-9#0')"
        )
        await asyncio.sleep(1.2)
        host_height = await page.evaluate("document.getElementById('host').offsetHeight")
        await browser.close()

    assert host_height == 0


_GREEDY = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><p>tiny</p><script>
  setInterval(() => parent.postMessage({type: 'wusool:frame-height', height: 9e9}, '*'), 50);
</script></body></html>"""


async def test_a_bundle_cannot_ask_for_an_absurd_frame_height() -> None:
    await _require_chromium()
    loader = (static_dir() / "shared" / "interactive.js").read_text(encoding="utf-8")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        await page.route(
            "http://test.local/page", lambda r: r.fulfill(content_type="text/html", body=_PAGE)
        )
        await page.route(
            "http://test.local/bundle.html",
            lambda r: r.fulfill(
                content_type="text/html", body=_GREEDY, headers={"access-control-allow-origin": "*"}
            ),
        )
        await page.goto("http://test.local/page")
        await page.add_script_tag(content=loader)
        await page.evaluate(
            "() => WusoolInteractive.mount(document.getElementById('host'), "
            "'http://test.local/bundle.html')"
        )
        await asyncio.sleep(1)
        height = await page.evaluate("document.querySelector('iframe').offsetHeight")
        await browser.close()

    assert height == 200000
