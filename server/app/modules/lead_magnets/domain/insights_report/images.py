"""Swaps a flattened report's base64 images for URLs, since Sanity rejects saves over 4 MB. Pure."""

import base64
import binascii
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
