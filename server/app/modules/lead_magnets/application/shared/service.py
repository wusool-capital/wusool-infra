"""The one composed application-layer facade for this module.

`bootstrap.py` builds exactly one of these per request or background job;
callers no longer construct `Pipelines` and `SubmissionService` separately
and wire one into the other by hand. Contains no business logic of its
own — both methods are a one-line delegation to `self._submissions`, which
is where the write contract actually lives.
"""

from uuid import UUID

from app.modules.lead_magnets.application.shared.base import ServiceBase
from app.modules.lead_magnets.domain.shared.tool_run import Tool, ToolRunRecord
from app.modules.utilities.domain.json_types import JsonObject


class LeadMagnetService(ServiceBase):
    async def record(
        self,
        *,
        tool: Tool,
        payload: JsonObject,
        email: str | None,
        domain: str | None,
        submission_id: str,
    ) -> tuple[UUID, bool]:
        return await self._submissions.record(
            tool=tool,
            payload=payload,
            email=email,
            domain=domain,
            submission_id=submission_id,
        )

    async def complete(self, run: ToolRunRecord) -> None:
        await self._submissions.complete(run)
