"""Port for recording a business event into the `activities` index."""

from typing import Protocol

from app.modules.activities.domain.event import ActivityEvent


class ActivityRecorderPort(Protocol):
    async def record(self, event: ActivityEvent) -> None:
        """Record `event` on the caller's transaction.

        Must never raise: an activity failure cannot abort the business write
        it describes.
        """
        ...
