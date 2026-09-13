"""`embed.js`'s TOOLS map is the whole cutover/rollback mechanism — a stale
entry here is invisible until a real embed fails, so it's checked directly
against `static_dir()` rather than trusted by eye.
"""

import re

from app.modules.lead_magnets.api.static import static_dir


def _tools_map() -> dict[str, str]:
    js = (static_dir() / "embed.js").read_text()
    start = js.index("var TOOLS = {")
    end = js.index("\n  };", start)
    block = js[start:end]
    return dict(re.findall(r'(\w+):\s*"([^"]+)"', block))


def test_every_tool_entry_resolves_to_a_real_index_html() -> None:
    tools = _tools_map()
    assert tools, "TOOLS map is empty or the parser above no longer matches embed.js"
    for name, src in tools.items():
        assert src.endswith("/"), f"{name}'s src {src!r} should use the trailing-slash form"
        resolved = static_dir() / src.strip("/") / "index.html"
        assert resolved.is_file(), f"{name} points at {src}, no index.html there"


def test_iframe_src_is_built_absolute_from_tools_origin() -> None:
    """The map's paths (e.g. "/benchmark/") are root-relative. A bare
    `iframe.src = src` resolves against the *parent* page's own origin,
    not the tools host — on Webflow that silently sends the iframe to
    wusoolcapital.com/benchmark/ instead of the tools server, 404ing
    there instead of loading the tool. Caught locally: opening a plain
    file:// test page with the embed script produced exactly this — an
    iframe pointed at file:///benchmark/, nothing rendered.
    """
    js = (static_dir() / "embed.js").read_text()
    assert "iframe.src = toolsOrigin + src;" in js


def test_height_is_measured_from_body_not_the_document_element() -> None:
    """`documentElement.scrollHeight` is the scrolling element's scroll
    area, which inside an iframe can never report less than the iframe's
    own viewport. Every tool's first report was therefore just the height
    the iframe already had, the observer never fired again, and all four
    embeds sat pinned there with the rest of the form cut off. <body> is a
    plain auto-height block and measures the real content.
    """
    js = (static_dir() / "shared" / "height.js").read_text()
    assert "document.body.scrollHeight" in js
    assert "observe(document.body)" in js


def test_the_embed_carries_no_fixed_dimensions_and_can_still_scroll() -> None:
    """Three things that each turned a wrong height into unreachable
    content: a per-tool pixel `fallbackHeight`, `scrolling="no"` (which
    meant the clipped half of a lead form could not be scrolled to at
    all), and Webflow's own `height:100vh` on the container the iframe
    sits in. The placeholder is viewport-relative, scrolling is left at
    the default so a late height degrades to a scrollbar rather than a
    dead end, and the host container is forced back to auto.
    """
    js = (static_dir() / "embed.js").read_text()
    assert "fallbackHeight" not in js
    assert 'setAttribute("scrolling"' not in js
    assert not re.search(r'style\.height\s*=\s*"\d+px"', js)
    assert 'host.style.height = "auto";' in js
