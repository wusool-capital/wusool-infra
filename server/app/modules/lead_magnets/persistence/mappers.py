"""`tool_runs` row → domain record.

Its own file rather than inlined in the repository, matching `meetings` and
`matching_engine`: this is where the ORM type stops. `application/` only ever
sees `ToolRunRecord`, so a column rename cannot reach a use case.
"""

from app.models.tool_run import ToolRun
from app.modules.lead_magnets.domain.tool_run import ToolRunRecord, parse_tool


def to_tool_run_record(row: ToolRun) -> ToolRunRecord:
    payload = row.payload or {}
    return ToolRunRecord(
        id=row.id,
        # `tool_runs.tool` is plain text with no CHECK behind it, unlike
        # `status` — validated here so `Tool` stays honest.
        tool=parse_tool(row.tool),
        status=row.status,
        attempt_count=row.attempt_count,
        payload=payload,
        stage=payload.get("stage"),
    )
