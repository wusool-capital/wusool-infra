"""Live select-option lookup — never hardcode Attio option IDs, they're
workspace-specific and drift (confirmed by this codebase's own
`backfill-seller-intake-source.ps1`, which exists specifically because of
that risk). Matches its pattern verbatim: fetch the attribute's current
options, match by title, use `id.option_id`.
"""

import time

from ddl_commands.shared.attio.client import AttioClient

_CACHE_TTL_SECONDS = 300
_cache: dict[tuple[str, str], tuple[float, list[dict]]] = {}


class OptionNotFoundError(Exception):
    """Raised when no active (non-archived) option matches the requested title."""

    def __init__(self, attribute_slug: str, target_kind: str, title: str) -> None:
        self.attribute_slug = attribute_slug
        self.title = title
        super().__init__(
            f"No active option titled {title!r} on {target_kind} attribute {attribute_slug!r}"
        )


async def _fetch_options(
    client: AttioClient, target_kind: str, target_slug: str, slug: str
) -> list[dict]:
    """`target_kind` is `"objects"` (organizations) or `"lists"` (seller_role,
    buyer_role) — Attio attribute endpoints are namespaced by which of the
    two the attribute belongs to.
    """
    cache_key = (target_slug, slug)
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    response = await client.get(f"/{target_kind}/{target_slug}/attributes/{slug}/options")
    options = response.get("data", [])
    _cache[cache_key] = (now, options)
    return options


async def get_option_id(
    client: AttioClient, *, target_kind: str, target_slug: str, attribute_slug: str, title: str
) -> str:
    options = await _fetch_options(client, target_kind, target_slug, attribute_slug)
    for option in options:
        if option.get("is_archived"):
            continue
        if option.get("title") == title:
            return option["id"]["option_id"]
    raise OptionNotFoundError(attribute_slug, target_kind, title)
