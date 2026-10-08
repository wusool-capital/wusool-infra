"""A gated report as the rest of the module sees it. Pure — no vendor types.

`providers/sanity` builds a `ReportDocument` from the CMS response and
`providers/webflow` turns one into a Reports card; nothing in between
knows either vendor's field names.
"""

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Literal

from app.modules.lead_magnets.domain.benchmark.benchmark_routing import FREE_MAIL

_TAG = re.compile(r"<[^>]+>")
_STYLE_OR_SCRIPT = re.compile(r"<(style|script)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_WORDS_PER_MINUTE = 200

# "featured" pins the top of /reports; "banner" pins the home page bar.
Pin = Literal["featured", "banner"]


@dataclass(frozen=True)
class ReportDocument:
    slug: str
    title: str
    html: str
    # The published Sanity document id; pins are matched by id, since a draft can rename the slug.
    document_id: str
    excerpt: str | None = None
    # Where the free preview ends in `html`; set at publish, so readers never re-split.
    preview_end: int = 0
    published_at: str | None = None
    updated_at: str | None = None
    cover_url: str | None = None
    featured: bool = False
    banner_pinned: bool = False
    silo: str | None = None
    # The button at the end of the report page.
    cta_text: str | None = None
    cta_url: str | None = None

    @property
    def pins(self) -> list[Pin]:
        held: list[tuple[Pin, bool]] = [("featured", self.featured), ("banner", self.banner_pinned)]
        return [pin for pin, on in held if on]


@dataclass(frozen=True)
class LostPins:
    """Pins just unticked on another report, which its Webflow card must drop too."""

    slug: str
    pins: tuple[Pin, ...]


@dataclass(frozen=True)
class ReportSource:
    """The HTML as the editor pasted it, and which version was last flattened."""

    document_id: str
    revision: str
    html: str
    rendered_from: str | None


# Bump when the renderer's output changes, so published reports are flattened again.
RENDER_VERSION = "5"


def fingerprint(html: str) -> str:
    """Identifies one version of a report's source HTML, so it is flattened once."""
    return hashlib.sha256(f"{RENDER_VERSION}\n{html}".encode()).hexdigest()


def word_count(html: str) -> int:
    return len(_TAG.sub(" ", _STYLE_OR_SCRIPT.sub(" ", html)).split())


def reading_time(html: str) -> str:
    return f"{max(1, math.ceil(word_count(html) / _WORDS_PER_MINUTE))} min read"


def org_domain(email: str) -> str | None:
    """Free-mail domains are left out: every Gmail reader would otherwise
    dedup onto one shared "gmail.com" organisation."""
    domain = email.rpartition("@")[2].strip().lower()
    if not domain or domain in FREE_MAIL:
        return None
    return domain
