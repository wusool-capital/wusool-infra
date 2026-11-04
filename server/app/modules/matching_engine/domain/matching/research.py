"""Full research on an approved discovered seller, kept on its candidate row:
the fields enrichment proposes, the LinkedIn scan, and which fields the
advisor saved. The web app shows it in place of Slack's proposal message.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from app.modules.utilities.domain.json_types import JsonObject

# What a proposed value can be once stored as JSON; dates travel as ISO strings.
ResearchValue = str | float | int | bool | list[str] | JsonObject
ResearchTarget = Literal["organization", "seller_role"]
ResearchStatus = Literal["running", "done", "failed"]


@dataclass(frozen=True)
class ResearchField:
    name: str
    target: ResearchTarget
    proposed: ResearchValue
    display: str
    confidence: float
    source_url: str
    rationale: str


@dataclass(frozen=True)
class ResearchPost:
    url: str
    text: str
    author_name: str | None = None
    posted_at: datetime | None = None


@dataclass(frozen=True)
class ResearchJobChange:
    name: str
    title: str | None
    company: str | None
    source_url: str


@dataclass(frozen=True)
class ResearchLinkedIn:
    outcome: Literal["completed", "skipped", "failed"]
    posts: tuple[ResearchPost, ...] = ()
    job_changes: tuple[ResearchJobChange, ...] = ()
    contacts_scanned: int = 0
    contacts_without_linkedin: int = 0


@dataclass(frozen=True)
class ResearchRecord:
    """`outcome` is None while the research runs; a claim with no outcome past
    the stale window was lost and can be retaken, like a run's discovery."""

    claimed_at: datetime
    outcome: Literal["done", "failed"] | None = None
    error: str | None = None
    fields: tuple[ResearchField, ...] = ()
    linkedin: ResearchLinkedIn | None = None
    saved_fields: tuple[str, ...] = ()
    skipped: bool = False
    saving_at: datetime | None = None

    def status(self, *, stale_before: datetime) -> ResearchStatus:
        if self.outcome is not None:
            return self.outcome
        return "failed" if self.claimed_at < stale_before else "running"

    def unsaved(self) -> tuple[ResearchField, ...]:
        return tuple(f for f in self.fields if f.name not in self.saved_fields)

    def with_saved(self, names: tuple[str, ...]) -> "ResearchRecord":
        return replace(
            self,
            saved_fields=tuple(dict.fromkeys((*self.saved_fields, *names))),
            saving_at=None,
        )
