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
    # Keys are bare identifiers except where the tool name has a hyphen
    # ("get-started"), which JavaScript requires be quoted — matching only
    # `\w+` would skip exactly those and pass this file by default.
    return dict(re.findall(r'"?([\w-]+)"?:\s*"([^"]+)"', block))


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


def test_tools_map_covers_every_served_tool_directory() -> None:
    """The reverse of the check above: a tool page that ships without a
    `TOOLS` entry is unreachable from Webflow, and nothing else notices."""
    served = {p.name for p in static_dir().iterdir() if p.is_dir() and (p / "index.html").is_file()}
    entries = {src.strip("/") for src in _tools_map().values()}
    assert entries == served


def test_modal_mode_returns_before_any_of_the_inline_path() -> None:
    """Modal mode must cost the four original tools nothing.

    It is an early return placed above every statement of the inline path,
    so a tag without `data-modal` runs exactly what it always has. If the
    branch ever moves below the iframe construction — or the inline path
    starts running first and unwinding — this fails.
    """
    js = (static_dir() / "embed.js").read_text()
    branch = js.index('if (script.hasAttribute("data-modal"))')
    assert branch < js.index("var iframe = document.createElement"), (
        "modal branch must precede the inline iframe construction"
    )
    assert branch < js.index("iframe.src = toolsOrigin + src;")
    assert branch < js.index("host.insertBefore(iframe, script);")


def test_only_the_inline_path_listens_for_height_messages() -> None:
    """A modal is a fixed overlay that scrolls internally, so it has no
    iframe to grow. Wiring `wusool:height` into it would resize the overlay
    to the document's height instead — and, worse, the listener would then
    be shared machinery the inline path depends on.
    """
    js = (static_dir() / "embed.js").read_text()
    assert js.count('data.type !== "wusool:height"') == 1
    listener = js.index('window.addEventListener("message"')
    modal_fn = js.index("function buildModal(")
    assert listener < modal_fn, "the height listener belongs to the inline path, above buildModal"


def test_modal_is_accessible_and_lazily_loaded() -> None:
    """Basics that are easy to drop and hard to notice: the dialog roles,
    Escape, focus restoration, and not fetching the form until it is
    actually opened.
    """
    js = (static_dir() / "embed.js").read_text()
    modal = js[js.index("function buildModal(") :]
    for needed in (
        '"role", "dialog"',
        '"aria-modal", "true"',
        'event.key === "Escape"',
        "lastFocused",
        "document.body.style.overflow",
    ):
        assert needed in modal, f"modal mode is missing {needed}"
    # The iframe is built inside openModal, not when the script runs.
    assert modal.index("frame = document.createElement") > modal.index("function openModal(")


def test_the_overlay_starts_hidden_and_stays_in_sync_with_display() -> None:
    """An inline `style="display:flex"` beats the UA stylesheet's
    `[hidden] { display: none }` rule — so an overlay built with both
    `hidden = true` *and* a baked-in `display:flex` is visible from the
    instant the page loads, on every page carrying the script, with no
    click at all. Caught live: the modal auto-opened on page load, covered
    the whole viewport (no `pointer-events` restriction), and made the
    entire site unclickable, because `openModal`/`closeModal` toggling
    `overlay.hidden` was doing nothing.

    `style.display` must be set explicitly in both `openModal` (to
    `"flex"`) and `closeModal` (to `"none"`), and the overlay's initial
    inline style must not claim `display:flex` before either has run.
    """
    js = (static_dir() / "embed.js").read_text()
    modal = js[js.index("function buildModal(") :]

    overlay_style = modal[modal.index("overlay.style.cssText") : modal.index("var panel")]
    assert "display:flex" not in overlay_style, "the overlay must not start visible"

    open_fn = modal[modal.index("function openModal(") : modal.index("function closeModal(")]
    assert 'overlay.style.display = "flex"' in open_fn

    close_fn = modal[modal.index("function closeModal(") : modal.index("close.addEventListener")]
    assert 'overlay.style.display = "none"' in close_fn
