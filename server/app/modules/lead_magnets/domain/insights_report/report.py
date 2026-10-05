"""A gated report as the rest of the module sees it. Pure — no vendor types.

`providers/sanity` builds a `ReportDocument` from the CMS response and
`providers/webflow` turns one into an Insights card; nothing in between
knows either vendor's field names.
"""

import hashlib
import math
import re
from dataclasses import dataclass

from app.modules.lead_magnets.domain.benchmark.benchmark_routing import FREE_MAIL

_TAG = re.compile(r"<[^>]+>")
_STYLE_OR_SCRIPT = re.compile(r"<(style|script)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_WORDS_PER_MINUTE = 200


@dataclass(frozen=True)
class ReportDocument:
    slug: str
    title: str
    html: str
    excerpt: str
    published_at: str | None = None
    updated_at: str | None = None
    cover_url: str | None = None
    featured: bool = False
    author: str | None = None
    silo: str | None = None


@dataclass(frozen=True)
class ReportSource:
    """The HTML as the editor pasted it, and which version was last flattened."""

    document_id: str
    html: str
    rendered_from: str | None


@dataclass(frozen=True)
class CmsItem:
    """An existing Insights card, reduced to what the sync decides on."""

    id: str
    gated: bool


def fingerprint(html: str) -> str:
    """Identifies one version of a report's source HTML, so it is flattened once."""
    return hashlib.sha256(html.encode()).hexdigest()


def reading_time(html: str) -> str:
    words = len(_TAG.sub(" ", _STYLE_OR_SCRIPT.sub(" ", html)).split())
    return f"{max(1, math.ceil(words / _WORDS_PER_MINUTE))} min read"


def org_domain(email: str) -> str | None:
    """Free-mail domains are left out: every Gmail reader would otherwise
    dedup onto one shared "gmail.com" organisation."""
    domain = email.rpartition("@")[2].strip().lower()
    if not domain or domain in FREE_MAIL:
        return None
    return domain
