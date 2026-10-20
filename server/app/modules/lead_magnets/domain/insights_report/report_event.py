"""One report submission or view, as the analytics seam receives it."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ReportEventName = Literal["report_code_requested", "report_unlocked", "report_viewed"]


@dataclass(frozen=True)
class ReportEvent:
    """Flat, so the gate form and a returning reader's cookie build it alike."""

    event: ReportEventName
    name: str
    email: str
    company: str
    domain: str | None
    slug: str
    report_title: str
    at: datetime
    format: Literal["html", "pdf"] | None = None
    # False when the email code is off: nobody has proven the address is theirs.
    email_verified: bool = True
