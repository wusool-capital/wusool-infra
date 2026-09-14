"""A `DiscoveredLead` turned into field values ready to prefill `/add-seller`'s
form — in Postgres's own value shape (matching what
`ddl_commands`'s `extract_field_value` returns), never Attio's write shape.
"""

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.modules.discovery.domain.leads import DiscoveredLead

# Every value this module actually writes is either `hq_country`'s bare
# string or `sector_focus`/`domains`' single-item list — narrower than
# `ddl_commands.api.schemas.PrefillValue` (which this module can't import;
# it lives in `ddl_commands.api`, and `discovery -> ddl_commands` isn't a
# real dependency edge — see this module's own `__init__.py`), so this
# bounds `SellerDraft.values` without reaching across the boundary.
DraftValue = str | list[str]


@dataclass(frozen=True)
class SellerDraft:
    org_name: str
    values: dict[str, DraftValue] = field(default_factory=dict)
    source_urls: tuple[str, ...] = ()


def _hostname(url: str) -> str | None:
    """Places' `websiteUri` is a full URL (scheme, and often a path) —
    Attio's `domains` attribute is domain-typed, so it wants a bare host,
    not `https://acme.example.com/contact`. Mirrors the `www.`/trailing-dot
    stripping `lead_magnets.domain.shared.dedup.normalise_domain` already
    does for the same column, kept local rather than reaching across the
    module boundary for two lines of logic.

    `urlsplit` raises `ValueError` on a handful of malformed inputs (an
    unbalanced IPv6-bracket host, e.g. `"http://[::1"`) rather than just
    returning no hostname — Places gives no format guarantee on `websiteUri`,
    so this degrades the same way every other bad-input case here does
    (no domain prefilled) instead of raising out of `draft_from_lead` and
    depending on the Slack handler's own blanket `except Exception` to
    catch it.
    """
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    return host.removeprefix("www.").rstrip(".") or None


def draft_from_lead(lead: DiscoveredLead) -> SellerDraft:
    """`lead.address` is a street address, not a country — there is no
    organization field it maps onto, so it isn't prefilled at all (rather
    than being stuffed into the wrong one). `lead.country`, from Places'
    `addressComponents`, does map onto `hq_country` — a plain string, since
    `hq_country` is `multi_select_as_text` (contrast `sector_focus` below,
    which takes a list). `category` is a free-text Google Places business
    type; it's offered as a `sector_focus` guess, but the add-form's
    prefill normalization silently drops it if it isn't one of the fixed
    sector options. `lead.website` maps onto `domains` (`text_list` — a
    list, like `sector_focus`, not a bare string like `hq_country`) as a
    bare hostname, via `_hostname`.
    """
    values: dict[str, DraftValue] = {}
    if lead.category:
        values["sector_focus"] = [lead.category]
    if lead.country:
        values["hq_country"] = lead.country
    if lead.website and (domain := _hostname(lead.website)):
        values["domains"] = [domain]
    return SellerDraft(org_name=lead.name, values=values, source_urls=(lead.source_url,))
