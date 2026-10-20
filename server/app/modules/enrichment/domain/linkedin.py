"""What a LinkedIn scan of a role's contacts yields, plus the pure job-change
rule. No vendor shape lives here — `providers/apify` maps into these types.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.modules.enrichment.domain.targets import EnrichmentTarget

LINKEDIN_PROVIDER_NAME = "LinkedIn (Apify)"

_INTRA_WORD = re.compile(r"[.'’]")
_NON_ALNUM = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")
_PROFILE_KEY = re.compile(r"linkedin\.com/in/([^/?#]+)", re.IGNORECASE)


@dataclass(frozen=True)
class Contact:
    person_attio_id: str
    name: str
    company_name: str
    linkedin_url: str | None = None
    job_title: str | None = None


@dataclass(frozen=True)
class LinkedInTargets:
    """A role's contacts (capped) and the company page to scrape alongside."""

    contacts: tuple[Contact, ...] = ()
    company_url: str | None = None


@dataclass(frozen=True)
class LinkedInProfile:
    url: str
    headline: str | None = None
    location: str | None = None
    current_title: str | None = None
    current_company: str | None = None


@dataclass(frozen=True)
class LinkedInPost:
    external_id: str
    url: str
    text: str
    author_name: str | None = None
    author_url: str | None = None
    posted_at: datetime | None = None


@dataclass(frozen=True)
class JobChange:
    contact: Contact
    profile: LinkedInProfile
    title_changed: bool
    company_changed: bool
    source_url: str
    provider: str = LINKEDIN_PROVIDER_NAME


class ScanOutcome(StrEnum):
    COMPLETED = "completed"
    # Nothing was scraped: no client, or no LinkedIn page saved for the org.
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class LinkedInScan:
    job_changes: tuple[JobChange, ...] = ()
    posts: tuple[LinkedInPost, ...] = ()
    # Skipped rather than scraped: a name-only lookup is expensive and
    # unreliable. Surfaced so an advisor can see who is missing.
    contacts_without_linkedin: tuple[Contact, ...] = ()
    contacts_scanned: int = 0
    outcome: ScanOutcome = ScanOutcome.COMPLETED

    @property
    def is_empty(self) -> bool:
        return not (self.job_changes or self.posts or self.contacts_without_linkedin)


@dataclass(frozen=True)
class ScanRecord:
    """Everything the history stores about one attempted scan."""

    target: EnrichmentTarget
    scan: LinkedInScan
    started_at: datetime
    finished_at: datetime
    # Slack user who triggered it; None when the system did.
    requested_by: str | None = None
    # The error type name of a scan that did not complete; None when it did.
    failure: str | None = None


def profile_key(url: str | None) -> str | None:
    """The `/in/<id>` part of a profile URL, so a stored URL and the one the
    vendor echoes back still match despite scheme, `www.` or trailing slash."""
    match = _PROFILE_KEY.search(url) if url else None
    return match.group(1).casefold() if match else None


def _normalise(value: str) -> str:
    # Dots and apostrophes join ("C.F.O." -> "cfo"); other punctuation separates.
    joined = _INTRA_WORD.sub("", value.casefold())
    return _WHITESPACE.sub(" ", _NON_ALNUM.sub(" ", joined)).strip()


def _same(known: str | None, scraped: str | None) -> bool:
    """A missing side means "unknown", never "changed". Containment counts as
    the same so "Acme" vs "Acme Holdings" doesn't read as a new employer."""
    if not known or not scraped:
        return True
    a, b = _normalise(known), _normalise(scraped)
    if not a or not b:
        return True
    return a == b or a in b or b in a


def detect_job_change(contact: Contact, profile: LinkedInProfile) -> JobChange | None:
    title_changed = not _same(contact.job_title, profile.current_title)
    company_changed = not _same(contact.company_name, profile.current_company)
    if not (title_changed or company_changed):
        return None
    return JobChange(
        contact=contact,
        profile=profile,
        title_changed=title_changed,
        company_changed=company_changed,
        source_url=profile.url,
    )


def job_change_key(change: JobChange) -> str:
    """A stable id for one detected move, so a re-scan doesn't report it twice.
    Stricter than `detect_job_change`, which also ignores containment."""
    title = _normalise(change.profile.current_title or "")
    company = _normalise(change.profile.current_company or "")
    basis = f"{title}|{company}"
    digest = hashlib.sha256(basis.encode()).hexdigest()[:16]
    return f"job_change:{change.contact.person_attio_id}:{digest}"
