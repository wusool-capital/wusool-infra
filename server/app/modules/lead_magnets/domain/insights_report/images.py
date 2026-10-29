"""Finds the base64 images a flattened report carries and swaps them for URLs. Pure.

An exported report embeds every picture as a `data:` URI, which is far past
Sanity's 4 MB save limit. The literal URI is replaced wherever it appears, so
`<img>`, `srcset`, `<image href>` and CSS `url(...)` are all covered at once.
"""

import base64
import re
from dataclasses import dataclass

# Fonts and non-base64 SVG URIs never match, so they stay inline.
_DATA_IMAGE = re.compile(r"data:(image/[A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/]+={0,2})")


@dataclass(frozen=True)
class DataImage:
    uri: str
    mime: str
    data: bytes


def data_images(html: str) -> list[DataImage]:
    """Each distinct embedded image once, in page order."""
    seen: dict[str, DataImage] = {}
    for match in _DATA_IMAGE.finditer(html):
        uri = match.group(0)
        if uri not in seen:
            seen[uri] = DataImage(
                uri=uri, mime=match.group(1), data=base64.b64decode(match.group(2), validate=True)
            )
    return list(seen.values())


def swap_images(html: str, urls: dict[str, str]) -> str:
    """`urls` maps each embedded URI to where it now lives."""
    return _DATA_IMAGE.sub(lambda match: urls.get(match.group(0), match.group(0)), html)
