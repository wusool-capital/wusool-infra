"""find_*, add_* and edit_* for buyers and sellers. Both kinds share one shape,
so each tool is registered from the same three functions."""

import json
import uuid
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.modules.ddl_commands import UploadKind, UploadRow, add_one, edit_one, find_records
from app.modules.mcp.api.runner import ToolRunner
from app.modules.mcp.api.tools.schemas import (
    AddResult,
    BuyerRow,
    EditResult,
    Fields,
    FindResult,
    Record,
    RequestId,
    SellerRow,
    field_guide,
)
from app.modules.mcp.domain.access import Caller, Permission

Query = Annotated[
    str, Field(min_length=2, max_length=200, description="Company name, or its domain")
]

_READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
_ADD = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
_EDIT = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False
)


_PERMISSIONS: dict[tuple[UploadKind, Literal["read", "write"]], Permission] = {
    ("buyer", "read"): "buyers.read",
    ("buyer", "write"): "buyers.write",
    ("seller", "read"): "sellers.read",
    ("seller", "write"): "sellers.write",
}


def register(server: MCPServer, runner: ToolRunner) -> None:
    _register_find(server, runner, "buyer")
    _register_find(server, runner, "seller")
    _register_add_buyer(server, runner)
    _register_add_seller(server, runner)
    _register_edit(server, runner, "buyer")
    _register_edit(server, runner, "seller")


def _register_find(server: MCPServer, runner: ToolRunner, kind: UploadKind) -> None:
    name = f"find_{kind}s"

    async def find(query: Query) -> FindResult:
        async def call(_: Caller) -> FindResult:
            return FindResult(records=[Record.of(r) for r in await find_records(kind, query)])

        return await runner.run(name, _PERMISSIONS[kind, "read"], call, output=FindResult)

    server.tool(
        name=name,
        title=f"Find {kind}s",
        description=(
            f"Look up {kind}s in the Wusool CRM by company name (similar names match) or by "
            f"exact domain. Use it to get the role_id before edit_{kind}.\n"
            f'Example: {{"query": "acme.com"}}'
        ),
        annotations=_READ,
    )(find)


def _register_add_buyer(server: MCPServer, runner: ToolRunner) -> None:
    async def add_buyer(buyer: BuyerRow, request_id: RequestId) -> AddResult:
        async def call(caller: Caller) -> AddResult:
            outcome = await add_one(
                "buyer",
                buyer.to_upload_row(),
                requested_by=caller.slack_user_id,
                invoked_via="mcp",
            )
            return AddResult.of(outcome)

        return await runner.run(
            "add_buyer",
            "buyers.write",
            call,
            output=AddResult,
            request_id=request_id,
            request_args=buyer.model_dump_json(),
        )

    server.tool(
        name="add_buyer",
        title="Add a buyer",
        description=(
            "Add a buyer to the Wusool CRM (Attio and Postgres), creating its company if new. "
            "A company is matched by domain: if it already has a buyer for this vertical, the "
            "existing record comes back with status 'existing' and nothing changes. An existing "
            "company's own fields are never changed.\n"
            'Example: {"buyer": {"org_name": "Acme Capital", "domain": "acme.com", '
            '"target_vertical": "Fintech", "fields": {"mandate_status": "Active"}}, '
            '"request_id": "6f1c..."}\n\n' + field_guide("buyer")
        ),
        annotations=_ADD,
    )(add_buyer)


def _register_add_seller(server: MCPServer, runner: ToolRunner) -> None:
    async def add_seller(seller: SellerRow, request_id: RequestId) -> AddResult:
        async def call(caller: Caller) -> AddResult:
            outcome = await add_one(
                "seller",
                seller.to_upload_row(),
                requested_by=caller.slack_user_id,
                invoked_via="mcp",
            )
            return AddResult.of(outcome)

        return await runner.run(
            "add_seller",
            "sellers.write",
            call,
            output=AddResult,
            request_id=request_id,
            request_args=seller.model_dump_json(),
        )

    server.tool(
        name="add_seller",
        title="Add a seller",
        description=(
            "Add a seller to the Wusool CRM (Attio and Postgres), creating its company if new. "
            "A company is matched by domain: if it already has a seller record, it comes back "
            "with status 'existing' and nothing changes. An existing company's own fields are "
            "never changed.\n"
            'Example: {"seller": {"org_name": "Gulf Clinics", "domain": "gulfclinics.sa", '
            '"fields": {"hq_country": "Saudi Arabia"}}, "request_id": "6f1c..."}\n\n'
            + field_guide("seller")
        ),
        annotations=_ADD,
    )(add_seller)


def _register_edit(server: MCPServer, runner: ToolRunner, kind: UploadKind) -> None:
    name = f"edit_{kind}"

    async def edit(
        role_id: Annotated[uuid.UUID, Field(description=f"The record's role_id from find_{kind}s")],
        fields: Fields,
        request_id: RequestId,
    ) -> EditResult:
        async def call(caller: Caller) -> EditResult:
            upload: UploadRow = {key: value for key, value in fields.items()}
            changed = await edit_one(
                kind, role_id, upload, requested_by=caller.slack_user_id, invoked_via="mcp"
            )
            return EditResult(role_id=role_id, changed_fields=list(changed))

        return await runner.run(
            name,
            _PERMISSIONS[kind, "write"],
            call,
            output=EditResult,
            request_id=request_id,
            request_args=json.dumps([str(role_id), fields], sort_keys=True),
        )

    server.tool(
        name=name,
        title=f"Edit a {kind}",
        description=(
            f"Change some fields of an existing {kind}, saved to Attio and Postgres straight "
            "away. Only the fields sent change. The company name and domain can't be edited"
            + (", and neither can target_vertical" if kind == "buyer" else "")
            + ".\n"
            'Example: {"role_id": "0b6e...", "fields": {"notes": "Met in Riyadh"}, '
            '"request_id": "6f1c..."}\n\n' + field_guide(kind)
        ),
        annotations=_EDIT,
    )(edit)
