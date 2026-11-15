"""Sends the Engine's role writes through `ddl_commands`, the same Attio-first
path Slack and the MCP use, so the Engine never writes Postgres alone."""

import uuid
from collections.abc import Sequence
from typing import Literal

from app.modules.crm.domain.roles import (
    BuyerChanges,
    Detail,
    FieldDef,
    FieldGroup,
    FieldKind,
    InvalidRoleFieldsError,
    NewBuyer,
    NewSeller,
    RoleNotFoundError,
    SellerChanges,
    WriteLandedPartlyError,
    appetite_signals,
    split_geographies,
)
from app.modules.ddl_commands import (
    BuyerNotFoundError,
    InvalidFieldsError,
    OrgMismatchError,
    OrgRemovedError,
    PartialWriteError,
    SellerNotFoundError,
    UploadRow,
    add_one,
    columns_for,
    edit_one,
    get_record,
    routes_for,
)
from app.modules.utilities.domain.safe_errors import describe_error

_BUYER_EDIT_KEYS = {
    "status": "mandate_status",
    "notes": "notes",
    "check_size_min_usd": "check_size_min",
    "check_size_max_usd": "check_size_max",
    "ebitda_floor_usd": "ebitda_floor",
}


def _geography_keys(
    picked: Sequence[str], regions: Sequence[str], countries: Sequence[str]
) -> UploadRow:
    """Only a group with a pick is sent: Attio's edit path skips nulls and refuses empty lists."""
    split = split_geographies(picked, regions, countries)
    row: UploadRow = {}
    if split.regions:
        row["target_region"] = list(split.regions)
    if split.countries:
        row["target_country"] = list(split.countries)
    return row


def buyer_add_row(
    buyer: NewBuyer, regions: Sequence[str] = (), countries: Sequence[str] = ()
) -> UploadRow:
    row: UploadRow = {
        "org_name": buyer.name,
        "domain": buyer.website,
        "target_vertical": buyer.sector,
    }
    optional = {
        "hq_country": buyer.hq,
        "mandate_status": buyer.status,
        "notes": buyer.notes,
        "check_size_min": buyer.check_size_min_usd,
        "check_size_max": buyer.check_size_max_usd,
        "ebitda_floor": buyer.ebitda_floor_usd,
    }
    row.update({key: value for key, value in optional.items() if value is not None})
    row.update(_geography_keys(buyer.geographies, regions, countries))
    row.update(detail_row(buyer.details))
    return row


def seller_add_row(seller: NewSeller) -> UploadRow:
    # `sector_focus` is the company's sector field in Attio; `hq_country` is its country list.
    row: UploadRow = {
        "org_name": seller.name,
        "domain": seller.website,
        "sector_focus": [seller.sector],
    }
    optional: UploadRow = {
        "hq_country": seller.hq,
        "appetite_signal": appetite_signals(seller.open_to_selling)[0]
        if seller.open_to_selling
        else None,
        "est_revenue": seller.est_revenue_usd,
        "est_ebitda": seller.est_ebitda_usd,
        "re_engage_date": seller.re_engage_date.isoformat() if seller.re_engage_date else None,
    }
    row.update({key: value for key, value in optional.items() if value is not None})
    row.update(detail_row(seller.details))
    return row


def buyer_edit_row(
    changes: BuyerChanges, regions: Sequence[str] = (), countries: Sequence[str] = ()
) -> UploadRow:
    row: UploadRow = {
        row_key: getattr(changes, field)
        for field, row_key in _BUYER_EDIT_KEYS.items()
        if field in changes.sent
    }
    if "geographies" in changes.sent:
        row.update(_geography_keys(changes.geographies, regions, countries))
    row.update(detail_row(changes.details))
    return row


def seller_edit_row(changes: SellerChanges) -> UploadRow:
    row: UploadRow = {}
    if "est_revenue_usd" in changes.sent:
        row["est_revenue"] = changes.est_revenue_usd
    if "est_ebitda_usd" in changes.sent:
        row["est_ebitda"] = changes.est_ebitda_usd
    if "open_to_selling" in changes.sent and changes.open_to_selling is not None:
        row["appetite_signal"] = appetite_signals(changes.open_to_selling)[0]
    if "re_engage_date" in changes.sent:
        row["re_engage_date"] = (
            changes.re_engage_date.isoformat() if changes.re_engage_date else None
        )
    return row


def _translated(exc: Exception) -> Exception:
    """The CRM's own error for what `ddl_commands` raised, or `exc` when it is neither."""
    match exc:
        case InvalidFieldsError():
            return InvalidRoleFieldsError(tuple(p.message for p in exc.problems))
        case BuyerNotFoundError() | SellerNotFoundError() | OrgRemovedError() | OrgMismatchError():
            return RoleNotFoundError(str(exc))
        case PartialWriteError():
            return WriteLandedPartlyError(tuple(exc.landed), describe_error(exc.cause))
    return exc


# Fields the Engine draws with its own controls, or that name the company; the rest are generic.
_OWN_BUYER_KEYS = frozenset(
    {
        "org_name",
        "domain",
        "target_vertical",
        "mandate_status",
        "notes",
        "ebitda_floor",
        "check_size_min",
        "check_size_max",
        "target_region",
        "target_country",
        "hq_country",
    }
)
_OWN_SELLER_KEYS = frozenset(
    {
        "org_name",
        "domain",
        "appetite_signal",
        "est_revenue",
        "est_ebitda",
        "re_engage_date",
        "hq_country",
    }
)
_KIND_BY_SPEC: dict[str, FieldKind] = {
    "text": "text",
    "multiline": "multiline",
    "select": "select",
    "multi_select_text": "multi_select",
    "multi_select_as_text": "multi_select",
    "currency": "currency",
    "percent": "percent",
    "number": "number",
    "date": "date",
    "bool": "bool",
}


def field_catalog(kind: Literal["buyer", "seller"]) -> tuple[FieldDef, ...]:
    skipped = _OWN_BUYER_KEYS if kind == "buyer" else _OWN_SELLER_KEYS
    routes = routes_for(kind)
    fields = []
    for column in columns_for(kind):
        # A kind with no entry here (a list of domains) has no generic control.
        if column.spec is None or column.field in skipped or column.spec.kind not in _KIND_BY_SPEC:
            continue
        group: FieldGroup = "role" if routes[column.field].target == "role" else "company"
        fields.append(
            FieldDef(
                key=column.field,
                label=column.label,
                kind=_KIND_BY_SPEC[column.spec.kind],
                options=tuple(column.spec.options or ()),
                group=group,
            )
        )
    return tuple(fields)


def detail_row(details: Sequence[Detail]) -> UploadRow:
    return {d.key: list(d.value) if isinstance(d.value, tuple) else d.value for d in details}


def _field_options(kind: Literal["buyer", "seller"], field: str) -> tuple[str, ...]:
    for column in columns_for(kind):
        if column.field == field and column.spec is not None:
            return tuple(column.spec.options or ())
    return ()


def _buyer_options(field: str) -> tuple[str, ...]:
    return _field_options("buyer", field)


class DdlCommandsRoleWriter:
    def buyer_statuses(self) -> tuple[str, ...]:
        return _buyer_options("mandate_status")

    def buyer_regions(self) -> tuple[str, ...]:
        return _buyer_options("target_region")

    def buyer_countries(self) -> tuple[str, ...]:
        return _buyer_options("target_country")

    def hq_countries(self) -> tuple[str, ...]:
        return _buyer_options("hq_country")

    def buyer_fields(self) -> tuple[FieldDef, ...]:
        return field_catalog("buyer")

    def seller_fields(self) -> tuple[FieldDef, ...]:
        return field_catalog("seller")

    async def record_details(
        self, kind: Literal["buyer", "seller"], role_id: str
    ) -> tuple[Detail, ...]:
        try:
            record = await get_record(kind, uuid.UUID(role_id))
        except (BuyerNotFoundError, SellerNotFoundError) as exc:
            raise _translated(exc) from exc
        wanted = {field.key for field in field_catalog(kind)}
        return tuple(
            Detail(key, tuple(value) if isinstance(value, list) else value)
            for key, value in record.fields.items()
            if key in wanted
        )

    def seller_sectors(self) -> tuple[str, ...]:
        return _field_options("seller", "sector_focus")

    async def add_seller(
        self, seller: NewSeller, *, requested_by: str
    ) -> tuple[Literal["added", "existing"], str]:
        try:
            outcome = await add_one(
                "seller", seller_add_row(seller), requested_by=requested_by, invoked_via="engine"
            )
        except (InvalidFieldsError, PartialWriteError) as exc:
            raise _translated(exc) from exc
        return outcome.status, str(outcome.record.role_id)

    async def add_buyer(
        self, buyer: NewBuyer, *, requested_by: str
    ) -> tuple[Literal["added", "existing"], str]:
        try:
            outcome = await add_one(
                "buyer",
                buyer_add_row(buyer, self.buyer_regions(), self.buyer_countries()),
                requested_by=requested_by,
                invoked_via="engine",
            )
        except (InvalidFieldsError, PartialWriteError) as exc:
            raise _translated(exc) from exc
        return outcome.status, str(outcome.record.role_id)

    async def edit_buyer(self, role_id: str, changes: BuyerChanges, *, requested_by: str) -> None:
        row = buyer_edit_row(changes, self.buyer_regions(), self.buyer_countries())
        await self._edit("buyer", role_id, row, requested_by)

    async def edit_seller(self, role_id: str, changes: SellerChanges, *, requested_by: str) -> None:
        await self._edit("seller", role_id, seller_edit_row(changes), requested_by)

    @staticmethod
    async def _edit(
        kind: Literal["buyer", "seller"], role_id: str, row: UploadRow, requested_by: str
    ) -> None:
        try:
            await edit_one(
                kind, uuid.UUID(role_id), row, requested_by=requested_by, invoked_via="engine"
            )
        except (
            InvalidFieldsError,
            BuyerNotFoundError,
            SellerNotFoundError,
            OrgRemovedError,
            OrgMismatchError,
            PartialWriteError,
        ) as exc:
            raise _translated(exc) from exc
