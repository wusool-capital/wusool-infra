"""Sanity CDN image URLs sized for Webflow, which fetches each image itself
and rejects anything over 4MB. Sanity resizes on its CDN from query params."""

from urllib.parse import urlsplit

_PARAMS = "?w=1600&fm=jpg"
_CDN_HOST = "cdn.sanity.io"


def resized(url: str) -> str:
    """Only bare Sanity CDN URLs: other hosts ignore the params, and a URL
    that already has a query was sized on purpose."""
    parts = urlsplit(url)
    if parts.hostname != _CDN_HOST or parts.query:
        return url
    return url + _PARAMS
