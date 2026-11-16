"""The daily post of what is still open for review."""

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
        """Items listed. Posts nothing when none are open."""
        items = await self._store.list_open()
        if not items:
            return 0
        await self._poster.post(_message(items))
        return min(len(items), _MAX_LISTED)


def _message(items: tuple[OpenReview, ...]) -> str:
    lines = [f"*Interactions engine: {len(items)} to review.* Each matched more than one record."]
    lines += [_line(item) for item in items[:_MAX_LISTED]]
    if len(items) > _MAX_LISTED:
        lines.append(f"…and {len(items) - _MAX_LISTED} more")
    return "\n".join(lines)


def _line(item: OpenReview) -> str:
    subject = (item.subject or "").strip()
    context = f" — {subject[:_SUBJECT_CHARS]}" if subject else ""
    return f"• {_LABEL[item.kind]} `{item.value}` ({item.record_count} records){context}"
