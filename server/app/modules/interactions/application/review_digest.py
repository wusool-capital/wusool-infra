"""The post about review cases that nobody has been told about yet."""

import logging

from app.modules.interactions.application.ports.review import (
    DigestPosterPort,
    OpenReview,
    ReviewStorePort,
)
from app.modules.interactions.domain.linking import Ambiguity

logger = logging.getLogger(__name__)

_MAX_LISTED = 20
_LABEL = {Ambiguity.SHARED_EMAIL: "shared address", Ambiguity.SHARED_DOMAIN: "shared domain"}
_SUBJECT_CHARS = 80


class ReviewDigestService:
    def __init__(self, store: ReviewStorePort, poster: DigestPosterPort) -> None:
        self._store = store
        self._poster = poster

    async def run(self) -> int:
        """Items listed. Posts only cases not listed before, so a restart repeats nothing."""
        items = await self._store.list_open()
        new = tuple(item for item in items if not item.notified)
        if not new:
            return 0
        listed = new[:_MAX_LISTED]
        await self._poster.post(_message(listed, len(new), len(items)))
        # Marked after the post, so a failed post is tried again.
        await self._store.mark_notified(listed)
        return len(listed)


def _message(listed: tuple[OpenReview, ...], new: int, total: int) -> str:
    lines = [
        f"*Interactions engine: {new} new to review* ({total} open in total). "
        "Each matched more than one record."
    ]
    lines += [_line(item) for item in listed]
    if new > len(listed):
        lines.append(f"…and {new - len(listed)} more, in the next post")
    return "\n".join(lines)


def _line(item: OpenReview) -> str:
    subject = (item.subject or "").strip()
    context = f" — {subject[:_SUBJECT_CHARS]}" if subject else ""
    return f"• {_LABEL[item.kind]} `{item.value}` ({item.record_count} records){context}"
