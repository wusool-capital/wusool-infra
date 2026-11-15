"""The extra fields the Slack forms take, drawn generically by the Engine."""

import pytest

from app.modules.crm.application.service import CrmService
from app.modules.crm.domain.roles import (
    BuyerChanges,
    BuyerFilters,
    Detail,
    InvalidRoleFieldsError,
    NewBuyer,
    NewSeller,
    SellerChanges,
    SellerFilters,
)
from app.modules.crm.providers.ddl_commands_writer import (
    buyer_add_row,
    buyer_edit_row,
    detail_row,
    field_catalog,
    seller_add_row,
)
from app.modules.crm.tests.unit.crm_fakes import JULES, FakeReader, FakeWriter


def _service() -> tuple[CrmService, FakeWriter]:
    reader = FakeReader()
    writer = FakeWriter(reader)
    return CrmService(reader, writer), writer


def test_the_buyer_catalog_has_the_slack_fields_with_the_right_controls() -> None:
    fields = {f.key: f for f in field_catalog("buyer")}

    assert fields["model"].kind == "select" and fields["model"].options
    assert fields["deal_structure_tolerance"].kind == "select"
    assert fields["earnout_tolerance"].kind == "bool"
    assert fields["investment_strategy"].kind == "multiline"
    assert fields["ev_ceiling"].kind == "currency"
    assert fields["last_mandate_briefing_date"].kind == "date"
    assert fields["client_type"].kind == "multi_select" and fields["client_type"].group == "company"
    assert fields["model"].group == "role"


def test_the_seller_catalog_has_the_slack_fields_with_the_right_controls() -> None:
    fields = {f.key: f for f in field_catalog("seller")}

    assert fields["sell_timeline"].kind == "select"
    assert fields["gross_margin_pct"].kind == "percent"
    assert fields["years_active"].kind == "number"
    assert fields["ebitda_deducts_salary"].kind == "bool"
    assert fields["org_relationship_status"].group == "company"
    assert fields["relationship_status"].group == "role"


@pytest.mark.parametrize("kind", ["buyer", "seller"])
def test_the_catalog_leaves_out_what_the_engine_draws_itself(kind: str) -> None:
    keys = [f.key for f in field_catalog(kind)]  # type: ignore[arg-type]

    assert len(keys) == len(set(keys))
    for own in ("org_name", "domain", "hq_country", "domains", "target_vertical"):
        assert own not in keys
    assert all(f.options for f in field_catalog(kind) if f.kind in {"select", "multi_select"})  # type: ignore[arg-type]
    assert {f.group for f in field_catalog(kind)} == {"role", "company"}  # type: ignore[arg-type]


def test_the_buyer_catalog_skips_fixed_controls_and_the_seller_one_its_own() -> None:
    buyer_keys = {f.key for f in field_catalog("buyer")}
    seller_keys = {f.key for f in field_catalog("seller")}

    assert not buyer_keys & {
        "notes",
        "mandate_status",
        "ebitda_floor",
        "check_size_min",
        "target_region",
    }
    assert not seller_keys & {"appetite_signal", "est_revenue", "est_ebitda", "re_engage_date"}


def test_checklist_values_become_lists_in_the_row() -> None:
    row = detail_row((Detail("client_type", ("M&A", "Project")), Detail("earnout_tolerance", True)))

    assert row == {"client_type": ["M&A", "Project"], "earnout_tolerance": True}


def test_details_travel_in_the_add_and_edit_rows() -> None:
    detail = (Detail("model", "Model 1"),)

    assert (
        buyer_add_row(NewBuyer(name="A", website="a.com", sector="Dental", details=detail))["model"]
        == "Model 1"
    )
    assert buyer_edit_row(BuyerChanges(frozenset({"details"}), details=detail)) == {
        "model": "Model 1"
    }
    assert (
        seller_add_row(NewSeller(name="A", website="a.com", sector="Clinic", details=detail))[
            "model"
        ]
        == "Model 1"
    )


async def test_the_first_pages_carry_the_catalog() -> None:
    service, _ = _service()

    buyers = await service.buyers(BuyerFilters(), None, 10)
    sellers = await service.sellers(SellerFilters(), None, 10)

    assert [f.key for f in buyers.options.fields] == ["model", "investment_strategy", "client_type"]
    assert [f.key for f in sellers.options.fields] == ["sell_timeline"]


async def test_one_role_read_carries_its_current_details_and_a_list_read_does_not() -> None:
    service, _ = _service()

    one = await service.buyer("b1")
    listed = (await service.buyers(BuyerFilters(), None, 10)).rows[0]

    assert one.details == (Detail("model", "Model 1"), Detail("client_type", ("M&A",)))
    assert listed.details == ()


async def test_a_detail_edit_is_written() -> None:
    service, writer = _service()

    await service.edit_buyer(
        JULES,
        "b1",
        BuyerChanges(frozenset({"details"}), details=(Detail("model", "Model 2"),)),
        '"v1"',
    )

    assert writer.changes[0].details == (Detail("model", "Model 2"),)


@pytest.mark.parametrize(
    ("details", "message"),
    [
        ((Detail("nope", "x"),), "nope is not a field"),
        ((Detail("model", None),), "Model cannot be cleared"),
        ((Detail("investment_strategy", ""),), "Investment strategy cannot be cleared"),
        ((Detail("client_type", ()),), "Client type cannot be cleared"),
        ((Detail("model", "Model 1"), Detail("model", "Model 2")), "model was sent twice"),
    ],
)
async def test_bad_details_are_refused_before_anything_is_written(
    details: tuple[Detail, ...], message: str
) -> None:
    service, writer = _service()

    with pytest.raises(InvalidRoleFieldsError, match=message):
        await service.edit_buyer(
            JULES, "b1", BuyerChanges(frozenset({"details"}), details=details), '"v1"'
        )

    assert writer.changes == []


@pytest.mark.parametrize("name", ["notes", "status", "ebitda_floor_usd", "check_size_min_usd"])
async def test_clearing_a_fixed_buyer_field_is_refused_because_attio_only_sets_values(
    name: str,
) -> None:
    service, writer = _service()

    with pytest.raises(InvalidRoleFieldsError, match="cannot be cleared here"):
        await service.edit_buyer(JULES, "b1", BuyerChanges(frozenset({name})), '"v1"')

    assert writer.changes == []


async def test_clearing_a_seller_date_or_amount_is_refused() -> None:
    service, _ = _service()

    with pytest.raises(InvalidRoleFieldsError, match="Re-engage date cannot be cleared"):
        await service.edit_seller(JULES, "s1", SellerChanges(frozenset({"re_engage_date"})), '"v1"')


async def test_a_new_buyer_with_an_unknown_detail_is_refused() -> None:
    service, _ = _service()

    with pytest.raises(InvalidRoleFieldsError, match="nope"):
        await service.add_buyer(
            JULES,
            NewBuyer(name="A", website="a.com", sector="Dental", details=(Detail("nope", "x"),)),
        )
