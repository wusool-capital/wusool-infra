"""The `meetings`-table persistence seam this module's use cases depend on.
Callers import this Protocol, never the concrete `MeetingsRepository` or any
SQLAlchemy type — implemented by
`app.modules.meetings.persistence.meetings_repository.MeetingsRepository`.
"""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.modules.meetings.domain.meeting_record import MeetingRecord, MeetingSyncStatus


class MeetingsRepositoryPort(Protocol):
    async def get_by_install_and_recording(
        self, install_id: str, local_recording_id: str
    ) -> MeetingRecord | None: ...

    async def create(
        self,
        *,
        id: UUID,
        org_id: str | None,
        org_name_raw: str | None,
        counterparty_role: str | None,
        meeting_type: str | None,
        occurred_at: datetime,
        title: str | None,
        source: str,
        duration_s: int | None,
        transcript: str | None,
        install_id: str | None,
        local_recording_id: str | None,
        status: str,
        metadata_: dict[str, Any] | None,
    ) -> MeetingRecord: ...

    async def mark_completed(
        self,
        meeting_id: UUID,
        *,
        summary_text: str,
        summary_json: dict[str, Any],
        title: str | None,
    ) -> None: ...

    async def mark_failed(self, meeting_id: UUID, *, reason: str) -> None: ...

    async def recover_stalled(self, meeting_id: UUID, *, cutoff: datetime) -> bool: ...

    async def get_by_id(self, meeting_id: UUID) -> MeetingRecord | None: ...

    async def list_by_install_id(
        self, install_id: str, *, limit: int
    ) -> list[MeetingSyncStatus]: ...
