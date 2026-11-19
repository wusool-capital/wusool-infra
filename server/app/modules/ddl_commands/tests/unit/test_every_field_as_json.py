"""Every field of a buyer and a seller, sent the way Claude sends it (JSON text), reaches
both writes in the type the field stores. A date sent as text crashed `serialize_date`;
this keeps the same gap from opening for any other field, kind or date."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.modules.ddl_commands.api.bulk_columns import FieldRoute, routes_for
from app.modules.ddl_commands.api.bulk_store import UploadKind
from app.modules.ddl_commands.api.bulk_upload import UploadRow, route_fields
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.schemas import FieldSpec
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.providers.attio import write_payload
from app.modules.ddl_commands.providers.attio.write_payload import (
    build_attio_values,
    build_postgres_values,
)

_ROLE_FIELDS: dict[UploadKind, dict[str, FieldSpec]] = {
    "buyer": BUYER_ROLE_FIELDS_BY_NAME,
    "seller": SELLER_ROLE_FIELDS_BY_NAME,
}
_ROLE_SLUG: dict[UploadKind, str] = {"buyer": "buyer_role", "seller": "seller_role"}
_ALL = [(kind, key) for kind in ("buyer", "seller") for key in routes_for(kind)]


def _json_value(spec: FieldSpec) -> str | list[str]:
    """What an agent sends: text for everything that is not a list."""
    first = spec.options[0] if spec.options else "x"
    return {
        "text": "Some text",
        "multiline": "Some text",
        "select": first,
        "multi_select_text": [first],
        "multi_select_as_text": [first],
        "currency": "5000000",
        "percent": "18",
        "number": "3",
        "date": "2026-01-31",
        "bool": "true",
    }[spec.kind]


@pytest.mark.parametrize("clearing", [False, True], ids=["add", "edit"])
@pytest.mark.parametrize(("kind", "key"), _ALL)
async def test_a_field_sent_as_json_is_typed_for_both_writes(
    monkeypatch: pytest.MonkeyPatch, kind: UploadKind, key: str, clearing: bool
) -> None:
    monkeypatch.setattr(write_payload, "get_option_id", AsyncMock(return_value="opt-1"))
    route: FieldRoute = routes_for(kind)[key]
    row: UploadRow = {key: _json_value(route.spec)}

    routed = route_fields(kind, 1, row, clearing=clearing)

    assert routed.problems == (), key
    extracted = routed.org_extracted if route.target == "org" else routed.role_extracted
    assert set(extracted) == {route.name}
    fields = ORGANIZATION_FIELDS_BY_NAME if route.target == "org" else _ROLE_FIELDS[kind]
    table = "organizations" if route.target == "org" else _ROLE_SLUG[kind]
    attio = await build_attio_values(
        AsyncMock(),
        target_kind="objects" if route.target == "org" else "lists",
        target_slug="organizations" if route.target == "org" else _ROLE_SLUG[kind],
        table=table,
        fields=fields,
        extracted=extracted,
    )
    postgres = build_postgres_values(table=table, fields=fields, extracted=extracted)

    assert attio and postgres
    stored = postgres[route.name]
    match route.spec.kind:
        case "date":
            assert stored == date(2026, 1, 31)
            assert attio[route.name] == "2026-01-31"
        case "currency":
            assert isinstance(stored, dict) and stored["amount"] == 5_000_000.0
        case "percent":
            assert stored == 18.0
        case "number":
            assert stored == 3 and isinstance(stored, int)
        case "bool":
            assert stored is True
        case "multi_select_as_text":
            assert isinstance(stored, str)
        case _:
            assert stored is not None


@pytest.mark.parametrize(
    ("kind", "key"), [(k, key) for k, key in _ALL if routes_for(k)[key].spec.kind == "date"]
)
async def test_every_date_field_can_be_emptied(kind: UploadKind, key: str) -> None:
    routed = route_fields(kind, 1, {key: None}, clearing=True)

    route = routes_for(kind)[key]
    extracted = routed.org_extracted if route.target == "org" else routed.role_extracted
    fields = ORGANIZATION_FIELDS_BY_NAME if route.target == "org" else _ROLE_FIELDS[kind]
    attio = await build_attio_values(
        AsyncMock(),
        target_kind="objects" if route.target == "org" else "lists",
        target_slug="organizations" if route.target == "org" else _ROLE_SLUG[kind],
        table="organizations" if route.target == "org" else _ROLE_SLUG[kind],
        fields=fields,
        extracted=extracted,
        clear_empty=True,
    )

    assert routed.problems == ()
    assert extracted == {route.name: None}
    assert attio == {route.name: []}  # Attio empties a scalar with an empty list


def test_the_date_fields_the_forms_have_are_the_ones_attio_dates_know() -> None:
    from app.modules.attio.providers.attio.dates import _PLAIN_DATE_FIELDS

    form_dates = {
        route.name
        for kind in ("buyer", "seller")
        for route in routes_for(kind).values()
        if route.spec.kind == "date"
    }

    assert form_dates <= _PLAIN_DATE_FIELDS
