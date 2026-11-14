"""Bulk import: preview a list, confirm it once the person agrees, follow progress."""

import uuid
from collections.abc import Sequence
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.modules.ddl_commands import (
    MAX_ROWS,
    PreviewResult,
    RejectedUpload,
    UploadKind,
    commit,
    preview_buyers,
    preview_sellers,
    status,
)
from app.modules.mcp.api.runner import ToolRunner
from app.modules.mcp.api.tools.schemas import (
    BuyerRow,
    ImportPreview,
    ImportProgress,
    Problem,
    RequestId,
    SellerRow,
    field_guide,
)
from app.modules.mcp.domain.access import Caller

PreviewId = Annotated[uuid.UUID, Field(description="preview_id from bulk_import_buyers/sellers")]

_PREVIEW = ToolAnnotations(read_only_hint=True, open_world_hint=False)
_CONFIRM = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


def _preview_result(result: PreviewResult | RejectedUpload) -> ImportPreview:
    if isinstance(result, RejectedUpload):
        return ImportPreview(
            accepted=False,
            invalid=result.invalid,
            problems=[Problem.of(p) for p in result.problems],
        )
    return ImportPreview(
        accepted=True,
        preview_id=result.preview_id,
        new=result.new,
        existing=result.existing,
        existing_rows=list(result.existing_rows),
    )


def _preview_description(kind: UploadKind, example_row: str) -> str:
    return (
        f"Check a list of 1 to {MAX_ROWS:,} {kind}s before adding them. Nothing is saved. "
        "Returns how many are new and how many already exist (matched by domain; those are "
        "skipped). If any row is invalid, the whole list is refused with every problem by row "
        "number: fix them and send the list again. Show the person the counts, and call "
        "confirm_import only after they say go.\n"
        f'Example: {{"rows": [{example_row}]}}\n\n' + field_guide(kind)
    )


def register(server: MCPServer, runner: ToolRunner) -> None:
    async def bulk_import_buyers(
        rows: Annotated[list[BuyerRow], Field(min_length=1, max_length=MAX_ROWS)],
    ) -> ImportPreview:
        return await _preview(runner, "bulk_import_buyers", "buyer", rows)

    async def bulk_import_sellers(
        rows: Annotated[list[SellerRow], Field(min_length=1, max_length=MAX_ROWS)],
    ) -> ImportPreview:
        return await _preview(runner, "bulk_import_sellers", "seller", rows)

    async def confirm_import(preview_id: PreviewId, request_id: RequestId) -> ImportProgress:
        async def call(caller: Caller) -> ImportProgress:
            return ImportProgress.of(
                preview_id, commit(preview_id, requested_by=caller.slack_user_id)
            )

        return await runner.run(
            "confirm_import",
            "imports.write",
            call,
            output=ImportProgress,
            request_id=request_id,
            request_args=str(preview_id),
        )

    async def get_import(preview_id: PreviewId) -> ImportProgress:
        async def call(caller: Caller) -> ImportProgress:
            return ImportProgress.of(
                preview_id, status(preview_id, requested_by=caller.slack_user_id)
            )

        return await runner.run("get_import", "imports.write", call, output=ImportProgress)

    server.tool(
        name="bulk_import_buyers",
        title="Preview a buyer list",
        description=_preview_description(
            "buyer",
            '{"org_name": "Acme Capital", "domain": "acme.com", "target_vertical": "Fintech"}',
        ),
        annotations=_PREVIEW,
    )(bulk_import_buyers)
    server.tool(
        name="bulk_import_sellers",
        title="Preview a seller list",
        description=_preview_description(
            "seller", '{"org_name": "Gulf Clinics", "domain": "gulfclinics.sa"}'
        ),
        annotations=_PREVIEW,
    )(bulk_import_sellers)
    server.tool(
        name="confirm_import",
        title="Confirm an import",
        description=(
            "Add the new rows of a previewed list, in the background (Attio first, then "
            "Postgres). Call it only after the person has said go. Returns at once; follow "
            "with get_import. Calling it again while it runs just returns the progress.\n"
            'Example: {"preview_id": "3b2f...", "request_id": "6f1c..."}'
        ),
        annotations=_CONFIRM,
    )(confirm_import)
    server.tool(
        name="get_import",
        title="Import progress",
        description=(
            "Progress of a confirmed import: added, skipped (already in the CRM) and failed "
            "rows with reasons. state is 'done' when finished.\n"
            'Example: {"preview_id": "3b2f..."}'
        ),
        annotations=_PREVIEW,
    )(get_import)


async def _preview(
    runner: ToolRunner, tool: str, kind: UploadKind, rows: Sequence[BuyerRow | SellerRow]
) -> ImportPreview:
    async def call(caller: Caller) -> ImportPreview:
        upload = [r.to_upload_row() for r in rows]
        preview = preview_buyers if kind == "buyer" else preview_sellers
        # Owned by the caller, so only they can confirm it or follow its progress.
        result = await preview(upload, invoked_via="mcp", owner=caller.slack_user_id)
        return _preview_result(result)

    return await runner.run(tool, "imports.write", call, output=ImportPreview)
