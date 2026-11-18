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

_READ = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)
_READ_PERMISSION: dict[UploadKind, Permission] = {
    "buyer": "buyers.read",
    "seller": "sellers.read",
}

RoleId = Annotated[uuid.UUID, Field(description="role_id from find_* or list_*")]
RoleIds = Annotated[
    list[uuid.UUID],
    Field(
        min_length=1,
        max_length=GET_IDS_MAX,
        description="role_ids from find_* or list_*; unknown ones come back in not_found",
    ),
]
Limit = Annotated[int, Field(ge=1, le=LIST_LIMIT_MAX, description="Most records to return")]
Offset = Annotated[
    int, Field(ge=0, description="Records to skip; use next_offset from the previous page")
]
Option = Annotated[
    str | None, Field(description="One allowed value; see list_field_options. Case is ignored")
]
Options = Annotated[
    list[str] | None,
    Field(description="Any of these allowed values; see list_field_options"),
]


def register(server: MCPServer, runner: ToolRunner) -> None:
    _register_get(server, runner, "buyer")
    _register_get(server, runner, "seller")
    _register_lists(server, runner)
    _register_check(server, runner)
    _register_field_options(server, runner)


def _register_get(server: MCPServer, runner: ToolRunner, kind: UploadKind) -> None:
    name = f"get_{kind}"

    async def get(role_ids: RoleIds) -> RecordDetails:
        async def call(_: Caller) -> RecordDetails:
            return RecordDetails.of(await get_records(kind, role_ids))

        return await runner.run(name, _READ_PERMISSION[kind], call, output=RecordDetails)

    server.tool(
        name=name,
        title=f"Get {kind}s",
        description=(
            f"Every field of up to {GET_IDS_MAX} {kind}s and their companies in one call, keyed "
            f"exactly like edit_{kind}'s `fields`, so read a value before changing it. To rank "
            f"or compare by numbers, pass the role_ids from list_{kind}s. Money is USD, "
            "dates YYYY-MM-DD, null means unset.\n"
            'Example: {"role_ids": ["0b6e...", "7c1d..."]}'
        ),
        annotations=_READ,
    )(get)


def _register_lists(server: MCPServer, runner: ToolRunner) -> None:
    async def list_buyers(
        target_vertical: Option = None,
        mandate_status: Option = None,
        model: Option = None,
        target_region: Options = None,
        target_country: Options = None,
        check_size_usd: Annotated[
            float | None,
            Field(gt=0, description="A deal size in USD that the buyer's check size fits"),
        ] = None,
        hq_country: Option = None,
        sector_focus: Options = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> RecordList:
        async def call(_: Caller) -> RecordList:
            found = await list_buyer_records(
                target_vertical=target_vertical,
                mandate_status=mandate_status,
                model=model,
                target_region=target_region or (),
                target_country=target_country or (),
                check_size_usd=check_size_usd,
                hq_country=hq_country,
                sector_focus=sector_focus or (),
                limit=limit,
                offset=offset,
            )
            return RecordList.of(found)

        return await runner.run("list_buyers", "buyers.read", call, output=RecordList)

    async def list_sellers(
        sector: Option = None,
        hq_country: Option = None,
        region: Option = None,
        relationship_status: Option = None,
        outreach_tier: Option = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> RecordList:
        async def call(_: Caller) -> RecordList:
            found = await list_seller_records(
                sector=sector,
                hq_country=hq_country,
                region=region,
                relationship_status=relationship_status,
                outreach_tier=outreach_tier,
                limit=limit,
                offset=offset,
            )
            return RecordList.of(found)

        return await runner.run("list_sellers", "sellers.read", call, output=RecordList)

    server.tool(
        name="list_buyers",
        title="List buyers",
        description=(
            "Active buyers matching every filter given, ordered by company name; rows hold "
            "ids only, so pass the role_ids to get_buyer for numbers. Region, country and "
            "sector_focus match when any value overlaps; sector_focus is the company's "
            "multi-value sector list, target_vertical its single vertical, so use "
            "sector_focus to catch buyers with the sector only there. check_size_usd keeps "
            "buyers whose check size range contains it; a buyer with no min or max set still "
            "matches, so confirm with get_buyer. If `truncated` is true, call again with "
            "offset=next_offset for the next page.\n"
            'Example: {"target_vertical": "Fintech", "target_country": ["United Arab Emirates"], '
            '"check_size_usd": 5000000}'
        ),
        annotations=_READ,
    )(list_buyers)
    server.tool(
        name="list_sellers",
        title="List sellers",
        description=(
            "Active sellers matching every filter given, ordered by company name; rows hold "
            "ids only, so pass the role_ids to get_seller for numbers. `sector` matches the "
            "company's sector focus. If `truncated` is true, call again with "
            "offset=next_offset for the next page.\n"
            'Example: {"sector": "Healthcare Services / Clinics", "hq_country": "Saudi Arabia"}'
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
    async def list_field_options(kind: Literal["buyer", "seller"]) -> FieldOptions:
        async def call(_: Caller) -> FieldOptions:
            return FieldOptions.of(kind)

        return await runner.run(
            "list_field_options", _READ_PERMISSION[kind], call, output=FieldOptions
        )

    server.tool(
        name="list_field_options",
        title="Field options",
        description=(
            "Every field a buyer or seller row accepts, with its type and allowed values. "
            "Use it to pick valid values for add, edit, bulk import and list filters.\n"
            'Example: {"kind": "buyer"}'
        ),
        annotations=_READ,
    )(list_field_options)
