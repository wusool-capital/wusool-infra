"""Contract checks for the split static pages.

Runs against whatever is actually committed under `static/` — as more tools
land, `test_every_script_and_stylesheet_ref_resolves` parametrizes over each
new `<tool>/index.html` automatically, no test edit required.
"""

import html as html_entities
import re
from pathlib import Path

import pytest

from app.modules.lead_magnets.api.schemas import (
    AnalyzeRequest,
    BenchmarkRequest,
    BuyerApplyRequest,
    CompareRequest,
    EnrichRequest,
    ReadinessRequest,
    ValuationRequest,
)
from app.modules.lead_magnets.api.static import static_dir

_EXTERNAL_HREF = re.compile(r"^https?://")
_TAG_REF = re.compile(r'<(?:script|link)\b[^>]*\b(?:src|href)="([^"]+)"')
_LEADING_KEY = re.compile(r"^\s*(?:\.\.\.\s*)?(\w+)")


def _payload_keys(js: str, marker: str) -> set[str]:
    """Top-level property names of the object literal that follows `marker`
    (e.g. `"const payload={"`), scanning by brace/paren/quote depth rather
    than assuming a one-key-per-line layout — tolerant of shorthand
    properties (`name` for `name: name`), nested calls, template literals,
    and a trailing spread.
    """
    start = js.index(marker) + len(marker)
    depth = 1  # already past the object literal's opening `{`
    quote: str | None = None
    keys: set[str] = set()
    seg_start = i = start
    while depth > 0:
        ch = js[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
            if depth == 0:
                break
        elif ch == "," and depth == 1:
            keys.add(_LEADING_KEY.match(js[seg_start:i]).group(1))
            seg_start = i + 1
        i += 1
    tail = js[seg_start:i].strip()
    if tail:
        keys.add(_LEADING_KEY.match(tail).group(1))
    return keys


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
    keys = _payload_keys(js, "const payload = {")
    assert keys == set(BenchmarkRequest.model_fields)


def test_readiness_payload_field_names_match_the_request_schema() -> None:
    js = (static_dir() / "readiness" / "30-submit.js").read_text()
    keys = _payload_keys(js, "const payload={")
    assert keys == set(ReadinessRequest.model_fields)


def test_valuation_payload_field_names_match_their_request_schemas() -> None:
    """Valuation has four call sites across two files, each posting to its
    own endpoint — checked independently since a shared helper would hide
    which one drifted."""
    components = (static_dir() / "valuation" / "30-components.js").read_text()
    enrich_start = components.index('fetch("/enrich"')
    enrich_keys = _payload_keys(components[enrich_start:], "body:JSON.stringify({")
    assert enrich_keys == set(EnrichRequest.model_fields)

    main = (static_dir() / "valuation" / "40-main.js").read_text()
    analyze_start = main.index('fetch("/analyze"')
    analyze_keys = _payload_keys(main[analyze_start:], "body:JSON.stringify({")
    # website_text is the one deliberate omission: the client-side scraping
    # that ever populated it was already dead in the live tool (see
    # 30-components.js's enrichFromDomain comment), so there was never a
    # real value to carry over. Every other field, including every
    # required one, must still be present.
    required = {name for name, field in AnalyzeRequest.model_fields.items() if field.is_required()}
    assert required <= analyze_keys
    assert analyze_keys <= set(AnalyzeRequest.model_fields)
    assert set(AnalyzeRequest.model_fields) - analyze_keys == {"website_text"}

    compare_start = main.index('fetch("/compare"')
    compare_keys = _payload_keys(main[compare_start:], "body:JSON.stringify({")
    assert compare_keys == set(CompareRequest.model_fields)

    submit_start = main.index('fetch("/submit-lead"')
    submit_keys = _payload_keys(main[submit_start:], "body:JSON.stringify({")
    # discounts is the one deliberate omission: TradingComps and
    # TransactionComps each keep their own independent user-adjustable
    # discount sliders, so there is no single unambiguous client-side
    # discount to forward - ValuationInputs already defaults to 50%/50%
    # when it's absent, the same as a sweeper resume with no model in
    # reach.
    required = {
        name for name, field in ValuationRequest.model_fields.items() if field.is_required()
    }
    assert required <= submit_keys
    assert submit_keys <= set(ValuationRequest.model_fields)
    assert set(ValuationRequest.model_fields) - submit_keys == {"discounts"}


def test_buyers_payload_field_names_match_the_request_schema() -> None:
    js = (static_dir() / "buyers" / "10-main.js").read_text()
    keys = _payload_keys(js, "const payload={")
    assert keys == set(BuyerApplyRequest.model_fields)


def test_buyers_select_options_match_the_live_validation_sets() -> None:
    """A stale `.ms-opt` here fails silently: the request schema itself
    doesn't validate `org_type`/`target_geography`/`sector_focus` (only the
    background Attio write does), so a typo'd option would record the lead
    and then just silently fail to land in the CRM."""
    from app.modules.lead_magnets.domain.buyer_network.buyer_network import (
        ORGANIZATION_TYPE_OPTIONS,
        TARGET_GEOGRAPHY_OPTIONS,
    )
    from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS

    html = (static_dir() / "buyers" / "index.html").read_text()

    def options_for(field_id: str) -> set[str]:
        # The widget is `<div class="ms" id="{field_id}">...</div>`, with
        # further nested `<div>`s inside (the list, each option row) — find
        # its true closing tag by depth, not the first `</div>` seen.
        marker = f'<div class="ms" id="{field_id}">'
        i = html.index(marker) + len(marker)
        depth = 1
        while depth > 0:
            next_open = html.find("<div", i)
            next_close = html.index("</div>", i)
            if next_open != -1 and next_open < next_close:
                depth += 1
                i = next_open + 4
            else:
                depth -= 1
                i = next_close + len("</div>")
        block = html[html.index(marker) : i]
        return {
            html_entities.unescape(v)
            for v in re.findall(r'class="ms-opt" data-value="([^"]*)"', block)
        }

    assert options_for("orgType") == ORGANIZATION_TYPE_OPTIONS
    assert options_for("targetGeography") == TARGET_GEOGRAPHY_OPTIONS
    assert options_for("sectorFocus") == SECTOR_FOCUS_OPTIONS


def test_readiness_results_escapes_model_generated_text_before_innerhtml() -> None:
    """`dim.name`/`dim.insight`/`rec.title`/`rec.detail` come straight from
    the `/readiness/score` Bedrock response and are spliced into
    `innerHTML` — unescaped, the prompt embedding the visitor's own
    free-text answers makes this a live XSS vector if the model ever echoes
    injected markup back."""
    js = (static_dir() / "readiness" / "40-results.js").read_text()
    assert "function esc(" in js
    for field in ("dim.name", "dim.insight", "rec.title", "rec.detail"):
        assert f"esc({field})" in js, f"{field} is interpolated into innerHTML unescaped"


def test_valuation_client_dcf_applies_the_same_dlom_as_the_server() -> None:
    """`domain/valuation/valuation_methods.py` always applies a 30% DLOM
    (`_DEFAULT_DLOM_PCT`) before reporting DCF equity value. Both client-side
    DCF calculations (`30-components.js`'s `DCFModule`, and `40-main.js`'s
    pre-calc that seeds it) must apply the same discount, or the interactive
    report a visitor reads shows a materially higher number than what is
    actually blended and written to Attio for the same submission."""
    helpers = (static_dir() / "valuation" / "20-helpers.js").read_text()
    assert "const DLOM_PCT=30;" in helpers

    components = (static_dir() / "valuation" / "30-components.js").read_text()
    assert "eqBeforeDlom*(1-DLOM_PCT/100)" in components

    main = (static_dir() / "valuation" / "40-main.js").read_text()
    assert "Math.max(dcfEV,0)*(1-DLOM_PCT/100)" in main


def test_benchmark_percent_validation_rejects_non_numeric_input() -> None:
    """`num(v)` returns `null` for non-numeric text, and JS coerces
    `null<0`/`null>100` to `false` — without an explicit `n===null` check,
    garbage input passed the 0-100 range check silently."""
    js = (static_dir() / "benchmark" / "30-helpers.js").read_text()
    assert "if(n===null||n<0||n>100)" in js
