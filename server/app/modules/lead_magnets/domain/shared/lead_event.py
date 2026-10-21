"""A lead submission or a Book a Call click, as the analytics seam receives it."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeGuard

LeadTool = Literal["benchmark", "buyer_network", "get_started", "readiness", "valuation"]
LeadEventName = Literal["lead_submitted", "book_call_clicked"]

_LEAD_TOOLS: frozenset[str] = frozenset(
    {"benchmark", "buyer_network", "get_started", "readiness", "valuation"}
)


def is_lead_tool(tool: str) -> TypeGuard[LeadTool]:
    return tool in _LEAD_TOOLS


@dataclass(frozen=True)
class LeadPerson:
    name: str
    email: str
    company: str


@dataclass(frozen=True)
class LeadEvent:
    event: LeadEventName
    tool: LeadTool
    # Random per page load, so it counts a lead without identifying anyone.
    submission_id: str
    at: datetime
    source: Literal["email"] | None = None
    # Set only when the visitor accepted tracking; without it the event is anonymous.
    person: LeadPerson | None = None
    visitor_id: str | None = None
