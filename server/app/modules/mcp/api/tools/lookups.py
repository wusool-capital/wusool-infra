"""Read-only tools: get one record, list records by filters, check a buyer's
profile, and the allowed values of each field."""

import uuid
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from app.modules.ddl_commands import (
    GET_IDS_MAX,
    LIST_LIMIT_MAX,
    RETURN_ALL_IDS_MAX,
    BuyerNotFoundError,
    UploadKind,
    get_record,
    get_records,
    list_buyer_records,
    list_seller_records,
)
from app.modules.discrepancies import check_buyer_by_id
from app.modules.mcp.api.runner import ToolRunner
from app.modules.mcp.api.tools.schemas import (
    BuyerCheck,
    FieldOptions,
    Gap,
    RecordDetails,
    RecordList,
)
from app.modules.mcp.domain.access import Caller, Permission
from app.modules.record_filters import MAX_FILTERS, FieldFilter

_READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)
_READ_PERMISSION: dict[UploadKind, Permission] = {
    "buyer": "buyers.read",
    "seller": "sellers.read",
}

_FIELD_KEYS_MAX = 200  # more than a buyer or seller has columns
RoleId = Annotated[uuid.UUID, Field(description="role_id from find_* or list_*")]
RoleIds = Annotated[
    list[uuid.UUID],
    Field(
        min_length=1,
        max_length=GET_IDS_MAX,
        description="role_ids from find_* or list_*; unknown ones come back in not_found",
    ),
]
FieldKeys = Annotated[
    list[str] | None,
    Field(
        max_length=_FIELD_KEYS_MAX,
        description="Field keys from list_field_options; omit for every editable field",
    ),
]
ReturnAll = Annotated[
    bool,
    Field(
        description=(
            f"Every column, for at most {RETURN_ALL_IDS_MAX} role_ids. Use only when the default "
            "template lacks what you need and `fields` can't name it; `fields` wins"
        )
    ),
]
Limit = Annotated[int, Field(ge=1, le=LIST_LIMIT_MAX, description="Most records to return")]
Filters = Annotated[
    list[FieldFilter] | None,
    Field(
        max_length=MAX_FILTERS,
        description=(
            "Filters on any field, all of which must match: {field, op, value}. Call "
            "list_field_options first for the field keys and, for a select or multi-select, its "
            "exact values; send only the fields you need. Ops by kind: select, text, multi-select "
            "take in/eq (text also contains); money, number, percent and date take gte/lte/eq; "
            "checkbox takes eq; every field takes is_set/is_not_set. gte/lte/eq never match a "
            "record with no value, so use is_set first to see how many have one. Money is USD."
        ),
    ),
]
Offset = Annotated[
    int, Field(ge=0, description="Records to skip; use next_offset from the previous page")
]


def register(server: MCPServer, runner: ToolRunner) -> None:
    _register_get(server, runner, "buyer")
    _register_get(server, runner, "seller")
    _register_lists(server, runner)
    _register_check(server, runner)
    _register_field_options(server, runner)


def _register_get(server: MCPServer, runner: ToolRunner, kind: UploadKind) -> None:
    name = f"get_{kind}"

    async def get(
        role_ids: RoleIds, fields: FieldKeys = None, return_all: ReturnAll = False
    ) -> RecordDetails:
        async def call(_: Caller) -> RecordDetails:
            return RecordDetails.of(
                await get_records(kind, role_ids, fields, return_all=return_all)
            )

        return await runner.run(name, _READ_PERMISSION[kind], call, output=RecordDetails)

    server.tool(
        name=name,
        title=f"Get {kind}s",
        description=(
            f"What an advisor needs to decide about up to {GET_IDS_MAX} {kind}s and their "
            "companies, in one call: the mandate, size, status, financials, relationship and "
            "company basics. Pass `fields` (keys from list_field_options) for exactly those, "
            "including computed columns you filtered on. Use `return_all` (every column) only "
            f"when the default lacks what you need and you can't name the fields; it takes at "
            f"most {RETURN_ALL_IDS_MAX} role_ids. "
            f"Before editing a field, read it with `fields`, as the keys match edit_{kind}'s "
            f"`fields`. To rank or compare by numbers, pass the role_ids from list_{kind}s. "
            "Money is USD, dates YYYY-MM-DD, null means unset.\n"
            'Example: {"role_ids": ["0b6e...", "7c1d..."], "fields": ["ebitda_ceiling"]}'
        ),
        annotations=_READ,
    )(get)


def _register_lists(server: MCPServer, runner: ToolRunner) -> None:
    async def list_buyers(
        filters: Filters = None, limit: Limit = 50, offset: Offset = 0
    ) -> RecordList:
        async def call(_: Caller) -> RecordList:
            found = await list_buyer_records(filters=filters or (), limit=limit, offset=offset)
            return RecordList.of(found)

        return await runner.run("list_buyers", "buyers.read", call, output=RecordList)

    async def list_sellers(
        filters: Filters = None, limit: Limit = 50, offset: Offset = 0
    ) -> RecordList:
        async def call(_: Caller) -> RecordList:
            found = await list_seller_records(filters=filters or (), limit=limit, offset=offset)
            return RecordList.of(found)

        return await runner.run("list_sellers", "sellers.read", call, output=RecordList)

    server.tool(
        name="list_buyers",
        title="List buyers",
        description=(
            "Active buyers matching every filter given, ordered by company name; no filter "
            "lists all. Rows hold ids only, so pass the role_ids to get_buyer for numbers. "
            "target_vertical is a buyer's single vertical; sector_focus is the company's "
            "multi-value sector list. A check size range that contains a deal size is two "
            "filters: check_size_min lte it and check_size_max gte it. If `truncated` is true, "
            "call again with offset=next_offset for the next page.\n"
            'Example: {"filters": [{"field": "target_vertical", "op": "eq", "value": "Fintech"}, '
            '{"field": "region", "op": "in", "value": ["GCC"]}, '
            '{"field": "ebitda_ceiling", "op": "gte", "value": 2000000}]}'
        ),
        annotations=_READ,
    )(list_buyers)
    server.tool(
        name="list_sellers",
        title="List sellers",
        description=(
            "Active sellers matching every filter given, ordered by company name; no filter "
            "lists all. Rows hold ids only, so pass the role_ids to get_seller for numbers. "
            "sector_focus is the company's sector list. If `truncated` is true, call again "
            "with offset=next_offset for the next page.\n"
            'Example: {"filters": [{"field": "sector_focus", "op": "eq", '
            '"value": "Healthcare Services / Clinics"}, '
            '{"field": "hq_country", "op": "eq", "value": "Saudi Arabia"}]}'
        ),
        annotations=_READ,
    )(list_sellers)


def _register_check(server: MCPServer, runner: ToolRunner) -> None:
    async def check_buyer(role_id: RoleId) -> BuyerCheck:
        async def call(_: Caller) -> BuyerCheck:
            await get_record("buyer", role_id)  # refuses unknown and inactive buyers
            result = await check_buyer_by_id(str(role_id), None)
            if result is None:
                raise BuyerNotFoundError(str(role_id))
            report = result.report
            return BuyerCheck(
                role_id=role_id,
                clear=report.is_clear,
                conflicts=[_gap(d.criterion, d.stored, d.stated) for d in report.conflicts],
                missing=[_gap(d.criterion, d.stored, d.stated) for d in report.missing],
                message=result.message,
            )

        return await runner.run("check_buyer", "buyers.read", call, output=BuyerCheck)

    server.tool(
        name="check_buyer",
        title="Check a buyer's profile",
        description=(
            "The same check as /check-buyer in Slack: which matching criteria the buyer's "
            "profile is missing or holds in conflict. Run it before matching or after an import, "
            "then fix gaps with edit_buyer.\n"
            'Example: {"role_id": "0b6e..."}'
        ),
        annotations=_READ,
    )(check_buyer)


def _gap(criterion: str, stored: str, stated: str | None) -> Gap:
    return Gap(criterion=str(criterion), stored=stored, stated=stated)


def _register_field_options(server: MCPServer, runner: ToolRunner) -> None:
    async def list_field_options(
        kind: Literal["buyer", "seller"], fields: FieldKeys = None
    ) -> FieldOptions:
        async def call(_: Caller) -> FieldOptions:
            return FieldOptions.of(kind, fields)

        return await runner.run(
            "list_field_options", _READ_PERMISSION[kind], call, output=FieldOptions
        )

    server.tool(
        name="list_field_options",
        title="Field options",
        description=(
            "Every field of a buyer or seller and its company: key, type, allowed values, "
            "whether it is editable, and the filter operators it takes. Pass `fields` for "
            "just those keys, for example to get a select's exact values before filtering "
            "on it. Use it to pick valid keys and values for add, edit, bulk import, get and "
            "list filters.\n"
            'Example: {"kind": "buyer", "fields": ["target_vertical", "ebitda_ceiling"]}'
        ),
        annotations=_READ,
    )(list_field_options)
