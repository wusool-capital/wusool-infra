"""The meeting-notes lookup interface `application/buyers.py` (and any other
concept needing recent-meeting context) depends on — implemented today by
`matching`'s own `MeetingRepository`. Kept here rather than duplicated per
consumer since it's one method, one contract.
"""

from typing import Protocol

from app.modules.matching_engine.domain.meetings import MeetingNote


class MeetingRepositoryPort(Protocol):
    async def get_recent_by_org(self, org_attio_id: str) -> list[MeetingNote]: ...
