"""Contract checks for the split static pages.

Runs against whatever is actually committed under `static/` — as more tools
land, `test_every_script_and_stylesheet_ref_resolves` parametrizes over each
new `<tool>/index.html` automatically, no test edit required.
"""

import re
from pathlib import Path

import pytest

from app.modules.lead_magnets.api.schemas import BenchmarkRequest
from app.modules.lead_magnets.api.static import static_dir

_EXTERNAL_HREF = re.compile(r"^https?://")
_TAG_REF = re.compile(r'<(?:script|link)\b[^>]*\b(?:src|href)="([^"]+)"')


def _local_refs(html: str) -> list[str]:
    return [ref for ref in _TAG_REF.findall(html) if not _EXTERNAL_HREF.match(ref)]


def _tool_dirs() -> list[Path]:
    return sorted(p for p in static_dir().iterdir() if p.is_dir() and (p / "index.html").is_file())


@pytest.mark.parametrize("tool_dir", _tool_dirs(), ids=lambda p: p.name)
def test_every_script_and_stylesheet_ref_resolves(tool_dir: Path) -> None:
    html = (tool_dir / "index.html").read_text()
    for ref in _local_refs(html):
        # Strip the release cache-buster (`?v=N`) before resolving to disk.
        path = ref.split("?", 1)[0]
        resolved = (tool_dir / path).resolve()
        assert resolved.is_file(), f"{tool_dir.name}/index.html references missing {ref}"


def test_no_committed_html_carries_inline_base64_images() -> None:
    """The whole point of `img/<sha8>.<ext>` extraction — a page that still
    embeds its own image defeats the year-long cache on img/ for nothing."""
    offenders = [
        html_file
        for html_file in static_dir().rglob("*.html")
        if "data:image/" in html_file.read_text()
    ]
    assert not offenders, offenders


def test_benchmark_payload_field_names_match_the_request_schema() -> None:
    """`BenchmarkRequest` is `extra="forbid"` — a page field renamed on one
    side and not the other 422s silently in prod, not at review time."""
    js = (static_dir() / "benchmark" / "60-render.js").read_text()
    start = js.index("const payload = {")
    end = js.index("\n  };", start)
    keys = set(re.findall(r"^\s*(\w+):", js[start:end], re.M))
    assert keys == set(BenchmarkRequest.model_fields)
