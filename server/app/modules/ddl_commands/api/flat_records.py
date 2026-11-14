"""Find, add and edit one buyer or seller from a flat field map: the shape the
Wusool MCP sends. A field map follows the bulk-upload row rules (`org_name`,
`domain`, then any organization or role field key), so one add and one bulk row
are checked and deduped the same way.
"""

import uuid
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import BuyerRole, Organization, SellerRole
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
from app.modules.ddl_commands.api.seller_edit import write_seller_edit
from app.modules.ddl_commands.application.buyers import (
    BuyerAlreadyExistsError,
    BuyerNotFoundError,
)
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
    """Changes only the fields sent; returns their keys. Raises
    `BuyerNotFoundError`/`SellerNotFoundError` for an unknown id."""
    routed = route_fields(kind, 1, fields)
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
