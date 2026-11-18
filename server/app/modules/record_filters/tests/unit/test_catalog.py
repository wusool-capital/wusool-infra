"""The catalog is read from the models: every data column, none of the internals."""

import pytest
from sqlalchemy.orm import class_mapper

from app.models import BuyerRole, Organization, SellerRole
from app.modules.record_filters import FieldMeta, RecordKind, build_catalog

_MODELS: dict[RecordKind, type[BuyerRole] | type[SellerRole]] = {
    "buyer": BuyerRole,
    "seller": SellerRole,
}
_INTERNAL = {"id", "raw_attio", "legacy_entry_id", "removed_at", "is_active"}


def _data_columns(model: type) -> set[str]:
    return {
        a.key
        for a in class_mapper(model).column_attrs
        if a.key not in _INTERNAL and not a.key.endswith("attio_id")
    }


@pytest.mark.parametrize("kind", ["buyer", "seller"])
def test_every_data_column_of_the_role_and_the_company_is_in_the_catalog(
    kind: RecordKind,
) -> None:
    catalog = build_catalog(kind, [])

    covered = {(f.target, f.column) for f in catalog.fields}
    expected = {("role", c) for c in _data_columns(_MODELS[kind])} | {
        ("org", c) for c in _data_columns(Organization)
    }
    assert covered == expected


@pytest.mark.parametrize("kind", ["buyer", "seller"])
def test_keys_are_unique_and_no_internal_column_is_offered(kind: RecordKind) -> None:
    catalog = build_catalog(kind, [])

    keys = [f.key for f in catalog.fields]
    assert len(keys) == len(set(keys))
    assert not {"raw_attio", "removed_at", "id", "legacy_entry_id", "org_attio_id"} & set(keys)
    assert not [k for k in keys if k.endswith("attio_id")]


def test_each_kind_of_column_gets_the_shape_of_its_storage() -> None:
    seller = build_catalog("seller", [])
    shapes = {f.column: f.shape for f in seller.fields if f.target == "role"}
    org_shapes = {f.column: f.shape for f in seller.fields if f.target == "org"}

    assert shapes["est_ebitda"] == "money"
    assert shapes["benchmark_score"] == "number"
    assert shapes["years_active"] == "number"
    assert shapes["re_engage_date"] == "date"
    assert shapes["created_at"] == "datetime"
    assert shapes["data_consent"] == "bool"
    assert shapes["sector"] == "array"
    assert shapes["outreach_tier"] == "text"
    assert org_shapes["funding_raised"] == "money"
    assert org_shapes["last_interaction_at"] == "datetime"
    assert org_shapes["sector_focus"] == "array"
    assert org_shapes["hq_country"] == "text"  # joined text only when the caller says so


def test_the_callers_fields_keep_their_keys_labels_and_options_and_are_editable() -> None:
    meta = [
        FieldMeta("region", "org", "region", "Region", ("GCC", "MENA"), joined_text=True),
        FieldMeta("ebitda_ceiling", "role", "ebitda_ceiling", "EBITDA ceiling"),
    ]

    catalog = build_catalog("buyer", meta)

    region = catalog.get("region")
    assert region is not None
    assert (region.shape, region.options, region.label, region.editable) == (
        "joined_text",
        ("GCC", "MENA"),
        "Region",
        True,
    )
    ceiling = catalog.get("ebitda_ceiling")
    assert ceiling is not None and ceiling.editable
    assert [f for f in catalog.fields if f.column == "region"] == [region]  # not added twice
    other = catalog.get("last_interaction_at")
    assert other is not None and other.editable is False


def test_a_column_name_both_tables_have_gets_a_prefixed_key() -> None:
    catalog = build_catalog(
        "buyer", [FieldMeta("ticket_size", "org", "ticket_size", "Ticket size")]
    )

    org_one = catalog.get("ticket_size")
    assert org_one is not None and org_one.target == "org"
    role_one = catalog.get("role_ticket_size")
    assert role_one is not None and (role_one.target, role_one.column) == ("role", "ticket_size")
    assert catalog.get("org_created_at") is not None
    assert catalog.get("created_at") is not None


def test_a_field_the_caller_names_on_a_missing_column_is_a_bug_not_a_silent_skip() -> None:
    with pytest.raises(KeyError):
        build_catalog("buyer", [FieldMeta("x", "role", "no_such_column", "X")])


def test_every_json_column_is_a_known_usd_money_column() -> None:
    """A JSONB column is filtered as `{amount, currency}` money. A new one must be
    checked, and added here, before it is offered as a range filter."""
    known = {
        "ebitda_floor",
        "check_size_min",
        "check_size_max",
        "ev_ceiling",
        "ebitda_ceiling",
        "estimated_aum",
        "est_revenue",
        "est_ebitda",
        "owner_salary",
        "valuation_low",
        "valuation_mid",
        "valuation_high",
        "revenue_last_full_year",
        "revenue_year_before",
        "annual_rent_cost",
        "implied_ev_low",
        "implied_ev_high",
        "ebitda_adjusted",
        "funding_raised",
    }
    found = {
        f.column
        for kind in ("buyer", "seller")
        for f in build_catalog(kind, []).fields
        if f.shape == "money"
    }

    assert found == known
