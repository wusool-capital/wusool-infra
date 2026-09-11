"""The Attio write seam. Faked in tests, implemented by
`providers/attio/role_writer.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs, Tool
from app.modules.utilities.domain.json_types import JsonObject


class AttioWriterPort(Protocol):
    """Writes the submission and its AI output to Attio and returns what it
    created. Attio first, Postgres second, always — a nightly job overwrites
    Postgres from Attio, so anything written straight to Postgres is
    destroyed on the next run.
    """

    async def write(self, *, tool: Tool, payload: JsonObject, ai: JsonObject) -> SubjectRefs: ...
