"""Swaps a flattened report's base64 images and fonts for URLs, and sizes the images for the
web. Sanity rejects saves over 4 MB and the free preview should be light. Pure."""

import base64
import binascii
import re
from dataclasses import dataclass

# Non-base64 SVG URIs never match, so they stay inline. Fonts go too: a report repeats the
# same few fonts in every style block, and as one URL the browser fetches each once.
_DATA_IMAGE = re.compile(r"data:((?:image|font)/[A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/]+={0,2})")
_SANITY_IMAGE = re.compile(r"(https://cdn\.sanity\.io/images/[^\s\"'()?&]+)(?![^\s\"'()]*\?)")
_WEB_SIZE = "?w=1200&fit=max&fm=webp&q=75"


@dataclass(frozen=True)
class DataImage:
    uri: str
    mime: str
    data: bytes


def data_images(html: str) -> list[DataImage]:
    """Each distinct embedded image once, in page order."""
    seen: dict[str, DataImage] = {}
    skipped: set[str] = set()
    for match in _DATA_IMAGE.finditer(html):
        uri = match.group(0)
        if uri in seen or uri in skipped:
            continue
        payload = match.group(2)
        try:
            data = base64.b64decode(payload + "=" * (-len(payload) % 4), validate=True)
        except binascii.Error:
            skipped.add(uri)  # left inline: a bad picture must not stop the report publishing
            continue
        seen[uri] = DataImage(uri=uri, mime=match.group(1), data=data)
    return list(seen.values())


def swap_images(html: str, urls: dict[str, str]) -> str:
    """`urls` maps each embedded URI to where it now lives."""
    return _DATA_IMAGE.sub(lambda match: urls.get(match.group(0), match.group(0)), html)


def web_images(html: str) -> str:
    """Sanity image URLs resized to the page's width as WebP. The pasted PNGs are far larger
    than the 794 px page that shows them."""
    # Vectors stay vectors; `fit=max` keeps small pictures from being enlarged.
    return _SANITY_IMAGE.sub(
        lambda match: (
            match.group(1) if match.group(1).endswith(".svg") else match.group(1) + _WEB_SIZE
        ),
        html,
    )
