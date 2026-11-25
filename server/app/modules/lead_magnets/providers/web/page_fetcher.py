"""Plain HTTPS fetch of a visitor-supplied URL, for `/enrich`'s meta description.

The URL comes from a public form, so this is an SSRF surface: https only,
every hop (the first request and each redirect) must resolve to public
addresses only, redirects are followed by hand and capped, the body is capped,
and the whole call is time-boxed. Any failure returns `""`, which makes the
caller fall back to Firecrawl.

shortcut: the address is checked at lookup, then httpx resolves again to
connect, so a DNS-rebinding host could differ between the two. Only the page's
meta description is ever returned, so the blast radius is small; pin the
resolved IP in a custom transport if that stops being acceptable.
"""

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlsplit

import httpx

logger = logging.getLogger(__name__)

_MAX_BYTES = 512 * 1024
_MAX_REDIRECTS = 3
_TOTAL_TIMEOUT_S = 5.0


async def _is_public_https(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return False
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, parts.port or 443, type=socket.SOCK_STREAM
        )
    except OSError:
        return False
    addresses = {str(info[4][0]).split("%")[0] for info in infos}
    return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)


class HttpPageFetcher:
    async def fetch_html(self, url: str) -> str:
        try:
            async with asyncio.timeout(_TOTAL_TIMEOUT_S):
                return await self._fetch(url)
        except Exception as exc:  # noqa: BLE001 - any failure just means "use the scrape path"
            logger.info("lead_magnet_page_fetch_failed url=%s reason=%s", url, type(exc).__name__)
            return ""

    async def _fetch(self, url: str) -> str:
        async with httpx.AsyncClient(follow_redirects=False, timeout=_TOTAL_TIMEOUT_S) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                if not await _is_public_https(url):
                    logger.warning("lead_magnet_page_fetch_blocked url=%s", url)
                    return ""
                async with client.stream("GET", url, headers={"Accept": "text/html"}) as response:
                    location = response.headers.get("location")
                    if response.is_redirect and location:
                        url = urljoin(url, location)
                        continue
                    if response.status_code != 200:
                        return ""
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) >= _MAX_BYTES:
                            break
                    return bytes(body[:_MAX_BYTES]).decode(response.encoding or "utf-8", "replace")
        return ""
