"""`embed.js`'s TOOLS map is the whole cutover/rollback mechanism — a stale
entry here is invisible until a real embed fails, so it's checked directly
against `static_dir()` rather than trusted by eye.
"""

import re

from app.modules.lead_magnets.api.static import static_dir


def _tools_map() -> dict[str, dict[str, object]]:
    js = (static_dir() / "embed.js").read_text()
    start = js.index("var TOOLS = {")
    end = js.index("\n  };", start)
    block = js[start:end]
    entries = {}
    for name, src, height in re.findall(
        r'(\w+):\s*\{\s*src:\s*"([^"]+)",\s*fallbackHeight:\s*(\d+)\s*\}', block
    ):
        entries[name] = {"src": src, "fallbackHeight": int(height)}
    return entries


def test_every_tool_entry_resolves_to_a_real_index_html() -> None:
    tools = _tools_map()
    assert tools, "TOOLS map is empty or the parser above no longer matches embed.js"
    for name, entry in tools.items():
        src = entry["src"]
        assert src.endswith("/"), f"{name}'s src {src!r} should use the trailing-slash form"
        resolved = static_dir() / src.strip("/") / "index.html"
        assert resolved.is_file(), f"{name} points at {src}, no index.html there"


def test_every_tool_entry_has_a_positive_fallback_height() -> None:
    for name, entry in _tools_map().items():
        assert entry["fallbackHeight"] > 0, name
