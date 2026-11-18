"""Find, add and edit one buyer or seller from a flat field map: the shape the
Wusool MCP sends. A field map follows the bulk-upload row rules (`org_name`,
`domain`, then any organization or role field key), so one add and one bulk row
are checked and deduped the same way.
"""

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import BuyerRole, Organization, SellerRole
from app.modules.ddl_commands.api.bulk_columns import match_option, routes_for
from app.modules.ddl_commands.api.bulk_store import InvokedVia, UploadKind
from app.modules.ddl_commands.api.bulk_upload import (
    RowProblem,
    UploadRow,
    add_row,
    host_of,
    match_row,
    parse_row,
    route_fields,
    write_lock,
)
from app.modules.ddl_commands.api.buyer_edit import write_buyer_edit
from app.modules.ddl_commands.api.dependencies import (
    ddl_commands_service,
    find_organization_by_domains,
    resolve_buyer_by_id,
    resolve_organization,
    resolve_seller_by_id,
)
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.seller_edit import write_seller_edit
from app.modules.ddl_commands.application.buyers import (
    BuyerAlreadyExistsError,
    BuyerNotFoundError,
)
from app.modules.ddl_commands.application.ports.buyers import BuyerFilters
from app.modules.ddl_commands.application.ports.sellers import SellerFilters
from app.modules.ddl_commands.application.sellers import (
    SellerAlreadyExistsError,
    SellerNotFoundError,
)


class InvalidFieldsError(Exception):
    """Nothing was written. `problems` names each bad field and why."""

    def __init__(self, problems: Sequence[RowProblem]) -> None:
        self.problems = tuple(problems)
        super().__init__("; ".join(p.message for p in self.problems))


class RecordRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    role_id: uuid.UUID
    org_attio_id: str
    org_name: str
    domains: tuple[str, ...]
    target_vertical: str | None = None  # buyers only


class AddOutcome(BaseModel):
    """`existing`: the company already holds this role, so nothing was written."""

    model_config = ConfigDict(frozen=True)

    status: Literal["added", "existing"]
    record: RecordRef


async def add_one(
    kind: UploadKind,
    row: UploadRow,
    *,
    requested_by: str | None,
    invoked_via: InvokedVia,
) -> AddOutcome:
    """Matches on the domain, like a bulk row. An existing organization without
    this role gets the new role, and its own fields are left as they are."""
    parsed = parse_row(kind, 1, row)
    if isinstance(parsed, list):
        raise InvalidFieldsError(parsed)
    vertical = parsed.role_extracted.get("target_vertical")
    vertical = vertical if isinstance(vertical, str) else None
    async with write_lock:
        match = await match_row(kind, parsed)
        status: Literal["added", "existing"] = "existing"
        if match.exists and match.org_attio_id is not None:
            org_attio_id = match.org_attio_id
        else:
            try:
                role = await add_row(kind, parsed, match, requested_by, invoked_via)
                org_attio_id, status = role.org_attio_id, "added"
            except (BuyerAlreadyExistsError, SellerAlreadyExistsError):
                # Raised only for an organization that already exists, so the match found it.
                if match.org_attio_id is None:
                    raise
                org_attio_id = match.org_attio_id
    ref = await _role_ref(kind, org_attio_id, vertical)
    if ref is None:
        raise LookupError(f"{kind} role for organization {org_attio_id} not found after add")
    return AddOutcome(status=status, record=ref)


async def edit_one(
    kind: UploadKind,
    role_id: uuid.UUID,
    fields: UploadRow,
    *,
    requested_by: str | None,
    invoked_via: InvokedVia,
) -> tuple[str, ...]:
    """Changes only the fields sent; a null or blank value empties that field. Returns their
    keys. Raises `BuyerNotFoundError`/`SellerNotFoundError` for an unknown id."""
    routed = route_fields(kind, 1, fields, clearing=True)
    problems = list(routed.problems)
    if not fields:
        problems.append(RowProblem(row=1, kind="required", message="send at least one field"))
    if "target_vertical" in fields:
        # As in Slack: moving a role could land it on a vertical another role holds.
        message = "target_vertical can't be changed; add a buyer for the other vertical"
        problems.append(
            RowProblem(row=1, kind="not_allowed", field="target_vertical", message=message)
        )
    if problems:
        raise InvalidFieldsError(problems)

    if kind == "buyer":
        buyer = await resolve_buyer_by_id(str(role_id))
        # An inactive row is a stale duplicate; Slack never offers one for editing either.
        if buyer is None or not buyer.is_active:
            raise BuyerNotFoundError(str(role_id))
        await write_buyer_edit(
            buyer_role_id=str(role_id),
            org_attio_id=buyer.org_attio_id,
            org_extracted=routed.org_extracted,
            role_extracted=routed.role_extracted,
            requested_by=requested_by,
            invoked_via=invoked_via,
        )
    else:
        seller = await resolve_seller_by_id(str(role_id))
        if seller is None or not seller.is_active:
            raise SellerNotFoundError(str(role_id))
        await write_seller_edit(
            seller_role_id=str(role_id),
            org_attio_id=seller.org_attio_id,
            org_extracted=routed.org_extracted,
            role_extracted=routed.role_extracted,
            requested_by=requested_by,
            invoked_via=invoked_via,
        )
    return tuple(sorted(fields))


async def find_records(kind: UploadKind, term: str) -> list[RecordRef]:
    """Active roles whose company domain matches `term` exactly, or else whose
    company name is similar to it, most similar first. A dotted name such as
    "Booking.com" falls back to the name search when no domain matches."""
    host = host_of(term) if "." in term and " " not in term.strip() else None
    if host is not None:
        org = await find_organization_by_domains([host, f"www.{host}"])
        with_roles = await resolve_organization(org.attio_id) if org is not None else None
        if with_roles is not None:
            return _refs(kind, with_roles)
    service = ddl_commands_service()
    if kind == "buyer":
        buyers = (await service.resolve_buyer(term)).candidates or []
        return [_ref(b, b.organization) for b in buyers]
    sellers = (await service.resolve_seller(term)).candidates or []
    return [_ref(s, s.organization) for s in sellers]


async def _role_ref(kind: UploadKind, org_attio_id: str, vertical: str | None) -> RecordRef | None:
    org = await resolve_organization(org_attio_id)
    if org is None:
        return None
    refs = _refs(kind, org)
    if kind == "buyer":
        refs = [r for r in refs if r.target_vertical == vertical]
    return refs[0] if refs else None


def _refs(kind: UploadKind, org: Organization) -> list[RecordRef]:
    roles: Sequence[BuyerRole | SellerRole] = (
        org.buyer_roles if kind == "buyer" else org.seller_roles
    )
    return [_ref(role, org) for role in roles if role.is_active]


def _ref(role: BuyerRole | SellerRole, org: Organization) -> RecordRef:
    return RecordRef(
        role_id=role.id,
        org_attio_id=org.attio_id,
        org_name=org.name,
        domains=tuple(org.domains),
        target_vertical=role.target_vertical if isinstance(role, BuyerRole) else None,
    )


FieldValue = str | float | bool | list[str] | None
LIST_LIMIT_MAX = 200
GET_IDS_MAX = 100  # a full record is ~60 fields; more than this overflows the caller's context


class RecordDetail(RecordRef):
    """Every field of one record, keyed like the field maps `edit_one` accepts.
    Money is a USD amount, dates are YYYY-MM-DD."""

    fields: dict[str, FieldValue]


class RecordDetails(BaseModel):
    """`not_found`: ids that are unknown, inactive, removed, or of the other kind."""

    model_config = ConfigDict(frozen=True)

    records: tuple[RecordDetail, ...]
    not_found: tuple[uuid.UUID, ...]


class RecordList(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: tuple[RecordRef, ...]
    truncated: bool  # more records match than were returned
    next_offset: int | None = None  # pass as `offset` to get the next page


async def get_record(kind: UploadKind, role_id: uuid.UUID) -> RecordDetail:
    """Raises `BuyerNotFoundError`/`SellerNotFoundError` for an unknown, inactive or
    removed record, the same records the lists leave out."""
    role: BuyerRole | SellerRole | None
    if kind == "buyer":
        role = await resolve_buyer_by_id(str(role_id))
        if role is None or not _is_live(role):
            raise BuyerNotFoundError(str(role_id))
    else:
        role = await resolve_seller_by_id(str(role_id))
        if role is None or not _is_live(role):
            raise SellerNotFoundError(str(role_id))
    return _detail(kind, role)


async def get_records(kind: UploadKind, role_ids: Sequence[uuid.UUID]) -> RecordDetails:
    """One query for all ids. Duplicates are dropped; results keep the input order."""
    ordered = tuple(dict.fromkeys(role_ids))
    ids = [str(role_id) for role_id in ordered]
    service = ddl_commands_service()
    found: Sequence[BuyerRole | SellerRole] = (
        await service.resolve_buyers_by_ids(ids)
        if kind == "buyer"
        else await service.resolve_sellers_by_ids(ids)
    )
    live = {uuid.UUID(str(role.id)): role for role in found if _is_live(role)}
    return RecordDetails(
        records=tuple(_detail(kind, live[role_id]) for role_id in ordered if role_id in live),
        not_found=tuple(role_id for role_id in ordered if role_id not in live),
    )


def _detail(kind: UploadKind, role: BuyerRole | SellerRole) -> RecordDetail:
    org = role.organization
    fields = {
        key: _plain(getattr(role if route.target == "role" else org, route.name))
        for key, route in routes_for(kind).items()
    }
    return RecordDetail(**_ref(role, org).model_dump(), fields=fields)


async def list_buyer_records(
    *,
    target_vertical: str | None = None,
    mandate_status: str | None = None,
    model: str | None = None,
    target_region: Sequence[str] = (),
    target_country: Sequence[str] = (),
    check_size_usd: float | None = None,
    hq_country: str | None = None,
    sector_focus: Sequence[str] = (),
    limit: int = 20,
    offset: int = 0,
) -> RecordList:
    """Select values match ignoring case; a value outside a field's options raises
    `InvalidFieldsError` naming the allowed values."""
    checker = _OptionChecker("buyer")
    filters = BuyerFilters(
        target_vertical=checker.one("target_vertical", target_vertical),
        mandate_status=checker.one("mandate_status", mandate_status),
        model=checker.one("model", model),
        target_region=checker.many("target_region", target_region),
        target_country=checker.many("target_country", target_country),
        check_size_usd=check_size_usd,
        hq_country=checker.one("hq_country", hq_country),
        sector_focus=checker.many("sector_focus", sector_focus),
    )
    checker.raise_problems()
    roles = await ddl_commands_service().list_buyers(filters, limit + 1, offset)
    return _record_list(roles, limit, offset)


async def list_seller_records(
    *,
    sector: str | None = None,
    hq_country: str | None = None,
    region: str | None = None,
    relationship_status: str | None = None,
    outreach_tier: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> RecordList:
    checker = _OptionChecker("seller")
    filters = SellerFilters(
        sector=checker.one("sector_focus", sector, name="sector"),
        hq_country=checker.one("hq_country", hq_country),
        region=checker.one("region", region),
        relationship_status=checker.one("relationship_status", relationship_status),
        outreach_tier=checker.one("outreach_tier", outreach_tier),
    )
    checker.raise_problems()
    roles = await ddl_commands_service().list_sellers(filters, limit + 1, offset)
    return _record_list(roles, limit, offset)


def _is_live(role: BuyerRole | SellerRole) -> bool:
    return bool(role.is_active) and role.removed_at is None and role.organization.removed_at is None


class InvalidFiltersError(InvalidFieldsError):
    """A list filter value is not allowed. Nothing was read; `problems` name the filter."""


class _OptionChecker:
    """Turns filter values into each field's own spelling, collecting every problem."""

    def __init__(self, kind: UploadKind) -> None:
        self._routes = routes_for(kind)
        self._problems: list[RowProblem] = []

    def one(self, key: str, value: str | None, *, name: str | None = None) -> str | None:
        """`name` is the filter as the caller knows it, when it differs from the field key."""
        if value is None:
            return None
        spec = self._routes[key].spec
        matched = match_option(spec, value)
        if matched is None:
            shown = name or key
            message = f"'{value}' is not allowed for {shown}. Allowed: {'; '.join(spec.options)}"
            self._problems.append(
                RowProblem(row=1, kind="not_allowed", field=shown, message=message)
            )
        return matched

    def many(self, key: str, values: Sequence[str]) -> tuple[str, ...]:
        return tuple(m for v in values if (m := self.one(key, v)) is not None)

    def raise_problems(self) -> None:
        if self._problems:
            raise InvalidFiltersError(self._problems)


def _record_list(roles: Sequence[BuyerRole | SellerRole], limit: int, offset: int) -> RecordList:
    truncated = len(roles) > limit
    return RecordList(
        records=tuple(_ref(role, role.organization) for role in roles[:limit]),
        truncated=truncated,
        next_offset=offset + limit if truncated else None,
    )


def _plain(value: PrefillValue | Decimal | None) -> FieldValue:
    """A stored column value in the shape Claude sends back to `edit_one`."""
    match value:
        case None | bool() | str():
            return value
        case int() | float() | Decimal():
            return float(value)
        case date():
            return value.isoformat()
        case list():
            return [str(item) for item in value]
        case dict():
            return _amount(value.get("amount"))
        case _:
            return str(value)


def _amount(amount: PrefillValue | None) -> float | None:
    """A stored money amount; legacy rows can hold it as a numeric string."""
    if isinstance(amount, bool):
        return None
    if isinstance(amount, int | float):
        return float(amount)
    if isinstance(amount, str):
        try:
            return float(amount)
        except ValueError:
            return None
    return None
