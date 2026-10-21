"""Where each tool's Book a Call button goes, and the tracked link emails use.

The redirect knows the calendar URLs, never the visitor: a URL taken from the
link would make it an open redirect.
"""

from urllib.parse import quote

from app.modules.lead_magnets.domain.shared.lead_event import LeadTool

_SELLER_CALENDAR = "https://calendar.app.google/UfXxu6dBkZ8wjhnT6"
_BUYER_CALENDAR = "https://calendar.app.google/4FzN5jAf5KGQszjY7"


def calendar_url(tool: LeadTool) -> str:
    return _BUYER_CALENDAR if tool == "buyer_network" else _SELLER_CALENDAR


def book_call_href(base_url: str, tool: LeadTool, submission_id: str) -> str:
    """The email button's link. Blank `base_url` keeps the direct calendar link."""
    if not base_url:
        return calendar_url(tool)
    return f"{base_url.rstrip('/')}/go/book-call/{tool}?sid={quote(submission_id, safe='')}"
