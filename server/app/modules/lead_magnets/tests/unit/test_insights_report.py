"""The gated report's pure pieces: the 25% cut, reading time, org domain."""

from app.modules.lead_magnets.domain.insights_report.report import org_domain, reading_time
from app.modules.lead_magnets.domain.insights_report.split import split_report

_WORDS = "word " * 100


def _doc(body: str) -> str:
    return (
        "<!doctype html><html><head><style>p{color:#000}</style></head>"
        f"<body>{body}</body></html>"
    )


def test_cut_falls_on_a_block_boundary_and_never_leaks_the_rest() -> None:
    blocks = "".join(f"<p>{n}{_WORDS}</p>" for n in "abcdefgh")
    html = _doc(blocks)

    preview, rest = split_report(html)

    assert preview + rest == html
    assert preview.endswith("</p>")
    assert rest.startswith("<p>")
    assert "a" + _WORDS in preview and "b" + _WORDS in preview
    assert "c" + _WORDS not in preview


def test_head_styles_always_stay_in_the_preview() -> None:
    preview, _ = split_report(_doc("".join(f"<p>{_WORDS}</p>" for _ in range(4))))

    assert "<style>p{color:#000}</style>" in preview


def test_a_single_wrapper_is_descended_into_before_cutting() -> None:
    """Without this, a report wrapped in one <div> would be all-or-nothing."""
    inner = "".join(f"<section>{n}{_WORDS}</section>" for n in "abcd")

    preview, rest = split_report(_doc(f'<div class="wrap">{inner}</div>'))

    assert preview.endswith("</section>")
    assert "a" + _WORDS in preview
    assert "d" + _WORDS in rest


def test_a_report_with_one_block_stays_fully_gated() -> None:
    preview, rest = split_report(_doc(f"<p>{_WORDS}</p>"))

    assert _WORDS not in preview
    assert _WORDS in rest


def test_the_last_block_is_never_the_cut() -> None:
    """A huge first block would otherwise put everything in the preview."""
    html = _doc(f"<p>{_WORDS * 20}</p><p>tail</p>")

    _, rest = split_report(html)

    assert "tail" in rest


def test_reading_time_ignores_markup_and_styles() -> None:
    html = "<style>" + "x " * 5000 + "</style>" + "<p>" + "w " * 401 + "</p>"

    assert reading_time(html) == "3 min read"
    assert reading_time("") == "1 min read"


def test_org_domain_comes_from_the_email_except_free_mail() -> None:
    assert org_domain("Dana@AcmeGroup.ae") == "acmegroup.ae"
    assert org_domain("dana@gmail.com") is None


def test_a_big_content_wrapper_beside_small_siblings_is_cut_inside() -> None:
    """Found in review: <header><main>everything</main><footer> used to cut
    after <main>, putting the whole report in the free preview."""
    paragraphs = "".join(f"<p>p{n} {_WORDS}</p>" for n in range(8))
    html = _doc(f"<header>T</header><main>{paragraphs}</main><footer>(c)</footer>")

    preview, rest = split_report(html)

    assert preview + rest == html
    assert [f"p{n} " in preview for n in range(8)] == [True, True] + [False] * 6


def test_inline_tags_are_never_a_cut_point() -> None:
    """Found in review: a <strong> inside a long paragraph was cut after,
    ending the preview mid-sentence."""
    long_paragraph = f"<p>{_WORDS * 3}<strong>bold</strong>{_WORDS * 3}</p>"
    html = _doc(f"<p>intro</p>{long_paragraph}<p>{_WORDS}</p><p>{_WORDS}</p>")

    preview, _ = split_report(html)

    assert preview.endswith("</p>")
    assert "<strong>bold</strong>" not in preview or preview.count("<p>") == preview.count("</p>")


def test_the_renderers_height_marker_wins_over_the_text_share() -> None:
    """The renderer knows the drawn layout; a tall image-heavy page carries
    little text, so a text share would put the gate too low."""
    html = _doc(
        f"<section>{_WORDS}</section><section data-wusool-gate>{_WORDS}</section>"
        f"<section>{_WORDS}</section>"
    )

    preview, rest = split_report(html)

    assert preview + rest == html
    assert rest.startswith("<section data-wusool-gate>")
