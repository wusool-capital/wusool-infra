"""A `DiscoveredLead` turned into field values ready to prefill `/add-seller`'s
form — in Postgres's own value shape (matching what
`ddl_commands`'s `extract_field_value` returns), never Attio's write shape.
"""

from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urlsplit

from app.modules.discovery.domain.leads import DiscoveredLead

# Mirrors `ddl_commands`' `PrefillValue` minus JSON objects; that module is
# off-limits to `discovery`.
DraftValue = str | float | bool | int | date | list[str]


@dataclass(frozen=True)
class SellerDraft:
    org_name: str
    values: dict[str, DraftValue] = field(default_factory=dict)
    source_urls: tuple[str, ...] = ()
    source_place_id: str | None = None


def hostname(url: str) -> str | None:
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
    # Diffbot/PDL homepages often arrive schemeless (`acme.com`), which
    # `urlsplit` would read as a path.
    if "://" not in url:
        url = f"//{url}"
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    host = (host or "").lower().removeprefix("www.").rstrip(".")
    # A dotless host (`not-a-url`) is free text, not a company domain.
    return host if "." in host else None


# ponytail: fixed list of social/site-builder hosts; extend as new platforms show up.
_PLATFORM_HOSTS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "youtube.com",
    "linktr.ee",
    "wa.me",
    "google.com",
    "wordpress.com",
    "squarespace.com",
    "wixsite.com",
    "business.site",
)


def company_hostname(url: str) -> str | None:
    """`hostname`, but `None` for a shared platform (an Instagram page, a
    `sites.google.com` site): that host names the platform, not the company."""
    host = hostname(url)
    if host is None or any(host == p or host.endswith(f".{p}") for p in _PLATFORM_HOSTS):
        return None
    return host


def websites_match(a: str, b: str) -> bool:
    """Same host, or one a subdomain of the other (`shop.acme.com` vs
    `acme.com`) — a near miss only costs an extra human review."""
    host_a, host_b = hostname(a), hostname(b)
    if not host_a or not host_b:
        return False
    return host_a == host_b or host_a.endswith(f".{host_b}") or host_b.endswith(f".{host_a}")


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
    bare hostname, via `hostname`.
    """
    values: dict[str, DraftValue] = {}
    if lead.category:
        values["sector_focus"] = [lead.category]
    if lead.country:
        values["hq_country"] = lead.country
    if lead.website and (domain := company_hostname(lead.website)):
        values["domains"] = [domain]
    return SellerDraft(
        org_name=lead.name,
        values=values,
        source_urls=(lead.source_url,),
        source_place_id=lead.place_id,
    )
