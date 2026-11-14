"""Column map and cell conversion for bulk upload files."""

import csv
import io
from datetime import UTC, date, datetime

import pytest

from app.modules.ddl_commands.api.bulk_columns import (
    CellError,
    CellValue,
    coerce_cell,
    columns_for,
    routes_for,
    template_csv,
)
from app.modules.ddl_commands.api.bulk_store import UploadKind
from app.modules.ddl_commands.api.schemas import FieldSpec, PrefillValue


def spec(kind: UploadKind, field: str) -> FieldSpec:
    column = next(c for c in columns_for(kind) if c.field == field)
    assert column.spec is not None
    return column.spec


@pytest.mark.parametrize("kind", ["buyer", "seller"])
def test_labels_are_unique_within_a_kind(kind: UploadKind) -> None:
    labels = [c.label.lower() for c in columns_for(kind)]

    assert len(labels) == len(set(labels))


def test_the_clashing_seller_label_is_renamed_and_the_organization_one_is_not() -> None:
    seller = {c.field: c.label for c in columns_for("seller")}
    buyer = {c.field: c.label for c in columns_for("buyer")}

    assert seller["relationship_status"] == "Seller relationship status"
    assert seller["org_relationship_status"] == "Relationship status"
    assert buyer["relationship_status"] == "Relationship status"
    assert "org_relationship_status" not in buyer


def test_only_a_shared_field_name_gets_the_org_prefix() -> None:
    prefixed = {k for k in routes_for("seller") if k.startswith("org_")}

    assert prefixed == {"org_relationship_status"}
    assert not {k for k in routes_for("buyer") if k.startswith("org_")}


def test_a_shared_name_routes_the_plain_key_to_the_role_and_the_prefixed_one_to_the_org() -> None:
    routes = routes_for("seller")

    role, org = routes["relationship_status"], routes["org_relationship_status"]
    assert (role.target, role.name) == ("role", "relationship_status")
    assert (org.target, org.name) == ("org", "relationship_status")
    assert role.spec.options != org.spec.options  # why one cell must not feed both


def test_required_columns_come_first() -> None:
    buyer = [c for c in columns_for("buyer") if c.required]
    seller = [c for c in columns_for("seller") if c.required]

    assert [c.label for c in buyer] == ["Organization name", "Domain", "Target vertical"]
    assert [c.label for c in seller] == ["Organization name", "Domain"]
    assert [c.label for c in columns_for("buyer")[:3]] == [c.label for c in buyer]


def test_the_domains_field_is_only_reachable_through_the_domain_column() -> None:
    assert "domains" not in {c.field for c in columns_for("buyer")}
    assert "domains" not in {c.field for c in columns_for("seller")}


@pytest.mark.parametrize("kind", ["buyer", "seller"])
def test_template_is_one_header_row_in_utf8_with_a_bom(kind: UploadKind) -> None:
    content = template_csv(kind)

    assert content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    assert rows == [[c.label for c in columns_for(kind)]]


@pytest.mark.parametrize(
    ("field", "raw", "expected"),
    [
        ("notes", "  Warm intro via a partner  ", "Warm intro via a partner"),
        ("notes", 2024.0, "2024"),
        ("ebitda_floor", "$1,250,000", 1250000.0),
        ("ebitda_floor", 750000, 750000.0),
        ("ebitda_floor", "1 250 000.50", 1250000.5),
        ("earnout_tolerance", "Yes", True),
        ("earnout_tolerance", "no", False),
        ("earnout_tolerance", True, True),
        ("last_mandate_briefing_date", "2026-03-31", date(2026, 3, 31)),
        ("last_mandate_briefing_date", date(2026, 3, 31), date(2026, 3, 31)),
        (
            "last_mandate_briefing_date",
            datetime(2026, 3, 31, 9, 30, tzinfo=UTC),
            date(2026, 3, 31),
        ),
        ("twitter_follower_count", "1200", 1200),
        ("twitter_follower_count", 1200.0, 1200),
    ],
)
def test_cells_become_the_value_the_add_form_produces(
    field: str, raw: CellValue, expected: PrefillValue
) -> None:
    kind: UploadKind = "buyer"
    result = coerce_cell(spec(kind, field), raw)

    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_an_empty_cell_is_unset(raw: CellValue) -> None:
    assert coerce_cell(spec("buyer", "notes"), raw) is None
    assert coerce_cell(spec("buyer", "ebitda_floor"), raw) is None


def test_percent_accepts_a_plain_number_or_a_percent_sign() -> None:
    gross_margin = spec("seller", "gross_margin_pct")

    assert coerce_cell(gross_margin, "35") == 35.0
    assert coerce_cell(gross_margin, "35%") == 35.0
    assert coerce_cell(gross_margin, 35.5) == 35.5


def test_a_select_matches_ignoring_case_and_returns_the_canonical_option() -> None:
    model = spec("buyer", "model")
    canonical = model.options[0]

    assert coerce_cell(model, canonical.upper()) == canonical
    assert coerce_cell(model, f"  {canonical.lower()} ") == canonical


def test_a_select_value_outside_its_options_is_refused_with_the_allowed_ones() -> None:
    model = spec("buyer", "model")

    with pytest.raises(CellError) as raised:
        coerce_cell(model, "Model 99")

    assert "Allowed:" in str(raised.value)
    assert model.options[0] in str(raised.value)


def test_a_long_option_list_is_shortened_in_the_message() -> None:
    vertical = spec("buyer", "target_vertical")
    assert len(vertical.options) > 8

    with pytest.raises(CellError) as raised:
        coerce_cell(vertical, "Not a vertical")

    assert str(raised.value).endswith("...")
    assert vertical.options[8] not in str(raised.value)


def test_a_multi_select_splits_on_semicolons_and_returns_canonical_options() -> None:
    sector = spec("buyer", "sector_focus")
    first, second = sector.options[0], sector.options[1]

    assert coerce_cell(sector, f"{first.lower()} ; {second}") == [first, second]
    assert coerce_cell(sector, f"{first};") == [first]


def test_a_multi_select_points_at_every_unknown_item_without_repeating_it() -> None:
    sector = spec("buyer", "sector_focus")

    with pytest.raises(CellError) as raised:
        coerce_cell(sector, f"{sector.options[0]};Nope;Also nope")

    message = str(raised.value)
    assert "item 2, 3" in message
    assert "Nope" not in message  # the problem list can be posted to a channel


def test_a_free_text_multi_select_is_joined_the_way_the_slack_form_joins_it() -> None:
    hq_country = spec("buyer", "hq_country")

    assert coerce_cell(hq_country, "UAE; Saudi Arabia ;Qatar") == "UAE, Saudi Arabia, Qatar"


@pytest.mark.parametrize(
    ("field", "raw", "message"),
    [
        ("ebitda_floor", "lots", "must be an amount"),
        ("ebitda_floor", "nan", "must be an amount"),
        ("ebitda_floor", True, "must be an amount"),
        ("twitter_follower_count", "12.5", "must be a whole number"),
        ("twitter_follower_count", "many", "must be a whole number"),
        ("last_mandate_briefing_date", "31/03/2026", "use the date format YYYY-MM-DD"),
        ("earnout_tolerance", "maybe", "use Yes or No"),
    ],
)
def test_a_bad_cell_is_refused_with_a_plain_message(
    field: str, raw: CellValue, message: str
) -> None:
    with pytest.raises(CellError) as raised:
        coerce_cell(spec("buyer", field), raw)

    assert str(raised.value) == message
