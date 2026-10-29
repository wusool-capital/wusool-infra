"""Swapping a flattened report's embedded images for URLs."""

import base64

import pytest

from app.modules.lead_magnets.domain.insights_report.images import data_images, swap_images


def _uri(payload: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(payload).decode()}"


def test_each_distinct_image_is_found_once_in_page_order() -> None:
    a, b = _uri(b"aaaa"), _uri(b"bbbb", "image/avif")
    html = f'<img src="{a}"><img src="{b}"><img src="{a}">'

    found = data_images(html)

    assert [(i.uri, i.mime, i.data) for i in found] == [
        (a, "image/png", b"aaaa"),
        (b, "image/avif", b"bbbb"),
    ]


def test_fonts_and_plain_svg_uris_are_left_inline() -> None:
    font = "<style>@font-face{src:url(data:font/woff2;base64,AAAA)}</style>"
    html = font + '<img src="data:image/svg+xml;utf8,<svg/>">'

    assert data_images(html) == []
    assert swap_images(html, {}) == html


def test_the_swap_reaches_attributes_and_css_alike() -> None:
    a = _uri(b"aaaa")
    html = f'<img src="{a}" srcset="{a} 2x"><style>.c{{background:url("{a}")}}</style>'

    swapped = swap_images(html, {a: "https://cdn.sanity.io/images/p/d/a.png"})

    assert "data:image" not in swapped
    assert swapped.count("https://cdn.sanity.io/images/p/d/a.png") == 3


def test_a_corrupt_payload_raises_rather_than_uploading_garbage() -> None:
    with pytest.raises(ValueError):
        data_images('<img src="data:image/png;base64,AAAAA=A">')
