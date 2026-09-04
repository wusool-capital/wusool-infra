"""The Slack-notification interface any module can depend on for out-of-band
outbound messaging (no live Slack request in flight) — implemented by
`providers/slack/notifier.py`. Not for in-request replies: Bolt's own
injected `client`/`ack`/`respond` already cover those (see this module's
README for the inbound-vs-outbound-vs-in-request distinction).

Stays on plain JSON shapes, not `slack_sdk`'s `Block`/`View` classes —
those are the provider's concern (`providers/slack/notifier.py` accepts
both); a Port other modules depend on shouldn't require them to import a
vendor SDK type. `Sequence` (covariant), not `list` (invariant), so a
caller's `list[dict[str, Any]]` is assignable regardless of how it was
built.
"""

from collections.abc import Sequence
from typing import Any, Protocol


class SlackNotifierPort(Protocol):
    async def post_message(
        self, *, channel: str, text: str, blocks: Sequence[dict[str, Any]] | None = None
    ) -> str:
        """Returns the posted message's `ts`, so a caller can `update_message` it later."""
        ...

    async def update_message(
        self,
        *,
        channel: str,
        ts: str,
        text: str,
        blocks: Sequence[dict[str, Any]] | None = None,
    ) -> None: ...

    async def open_view(self, *, trigger_id: str, view: dict[str, Any]) -> None: ...
