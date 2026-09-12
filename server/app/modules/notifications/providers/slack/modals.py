"""Placeholder modals every slash command opens *before* it does any work.

Slack invalidates a slash command's `trigger_id` 3 seconds after the command
is issued — and that clock starts when the operator hits enter, not when the
request reaches us, so network delivery, signature verification and `ack()`
are already spent before a handler runs. Every command here then ran a
database query (a name search) and only called `views_open` afterwards, which
made a successful modal a race: `/edit-buyer` died in production with
`expired_trigger_id` after a 2071ms handler, comfortably inside the 3s budget
as measured *from the handler*, but not as measured from the command.

The fix is to stop spending the trigger on anything: `views_open` a
placeholder the instant the handler starts, then `views_update` it with the
real content once the slow work finishes. `view_id` never expires, so the
query can take as long as it needs.

Usage errors (an empty command) are deliberately *not* routed through here —
they need no query, so they stay the ephemeral message they already were
rather than flashing a modal open and closed.
"""

from slack_sdk.models.blocks import SectionBlock
from slack_sdk.models.views import View
from slack_sdk.web.async_client import AsyncWebClient

# Slack rejects a view whose title exceeds this; see
# `ddl_commands/tests/unit/test_slack_view_limits.py` for the rest of them.
_MAX_TITLE = 24


def build_loading_modal(title: str) -> View:
    return View(
        type="modal",
        title=title[:_MAX_TITLE],
        close="Cancel",
        blocks=[SectionBlock(text=":hourglass_flowing_sand: _Searching…_")],
    )


def build_notice_modal(title: str, text: str) -> View:
    """Terminal state for a command that opened a modal and then found it had
    nothing to show (no match) or nothing more to do (work handed to a
    background task). Closing is the only action.
    """
    return View(
        type="modal",
        title=title[:_MAX_TITLE],
        close="Close",
        blocks=[SectionBlock(text=text)],
    )


async def open_loading_modal(client: AsyncWebClient, *, trigger_id: str, title: str) -> str:
    """Returns the `view_id` to hand to `views_update`. Call this before any
    query — every millisecond before it is charged against the trigger.
    """
    response = await client.views_open(trigger_id=trigger_id, view=build_loading_modal(title))
    return str(response["view"]["id"])
