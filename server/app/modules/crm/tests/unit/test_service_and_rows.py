from datetime import UTC, date, datetime

import pytest

from app.models import BuyerRole as BuyerRoleRow
from app.models import Organization
from app.models import SellerRole as SellerRoleRow
from app.modules.crm.api.schemas import (
    BuyerFilterQuery,
    BuyerUpdate,
    SellerFilterQuery,
    SellerUpdate,
    parse_range,
)
from app.modules.crm.application.service import MAX_PAGE_SIZE, CrmService
from app.modules.crm.domain.roles import (
    BuyerChanges,
    BuyerFilters,
    Detail,
    NewBuyer,
    NewSeller,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    SellerChanges,
    StaleRoleError,
    open_to_selling,
)
from app.modules.crm.persistence.mappers import to_buyer, to_seller
from app.modules.crm.providers.ddl_commands_writer import (
    buyer_add_row,
    buyer_edit_row,
    seller_add_row,
    seller_edit_row,
)
from app.modules.crm.tests.unit.crm_fakes import JULES, FakeReader, FakeWriter


def _service(**writer_args) -> tuple[CrmService, FakeReader, FakeWriter]:
    reader = FakeReader()
    writer = FakeWriter(reader, **writer_args)
    return CrmService(reader, writer), reader, writer


async def test_the_page_size_is_capped() -> None:
    service, reader, _ = _service()

    await service.buyers(BuyerFilters(), None, 5000)

    assert reader.seen_limits == [MAX_PAGE_SIZE]


async def test_a_duplicate_buyer_is_refused() -> None:
    service, _, _ = _service(add_outcome="existing")

    with pytest.raises(RoleAlreadyExistsError):
        await service.add_buyer(JULES, NewBuyer(name="Acme", website="acme.com", sector="Dental"))


async def test_an_edit_with_the_current_etag_goes_through_and_names_the_person() -> None:
    service, _, writer = _service()

    role = await service.edit_buyer(
        JULES, "b1", BuyerChanges(frozenset({"notes"}), notes="x"), '"v1"'
    )

    assert role.etag == "v2"
    assert writer.edits == [("b1", JULES.id)]


async def test_an_edit_with_a_stale_etag_writes_nothing() -> None:
    service, _, writer = _service()

    with pytest.raises(StaleRoleError):
        await service.edit_seller(
            JULES, "s1", SellerChanges(frozenset({"est_revenue_usd"})), '"old"'
        )

    assert writer.edits == []


async def test_an_unknown_role_is_not_found() -> None:
    service, _, _ = _service()

    with pytest.raises(RoleNotFoundError):
        await service.edit_buyer(JULES, "nope", BuyerChanges(frozenset({"notes"})), '"v1"')


def test_a_weak_etag_still_matches() -> None:
    from app.modules.crm.application.service import _same_version

    assert _same_version("v1", 'W/"v1"')


def test_buyer_add_row_sends_the_required_keys_and_only_the_given_optionals() -> None:
    row = buyer_add_row(
        NewBuyer(name="Acme", website="acme.com", sector="Dental", check_size_min_usd=1e6)
    )

    assert row == {
        "org_name": "Acme",
        "domain": "acme.com",
        "target_vertical": "Dental",
        "check_size_min": 1e6,
    }


def test_edit_rows_carry_only_sent_fields_and_clear_with_none() -> None:
    assert buyer_edit_row(BuyerChanges(frozenset({"notes", "status"}), status="Dormant")) == {
        "mandate_status": "Dormant",
        "notes": None,
    }
    assert seller_edit_row(
        SellerChanges(
            frozenset({"open_to_selling", "re_engage_date"}),
            open_to_selling="Warm intro",
            re_engage_date=date(2027, 1, 5),
        )
    ) == {
        "appetite_signal": "Warm Introduction / Direct Outreach",
        "re_engage_date": "2027-01-05",
    }


def test_seller_edit_rows_carry_the_extra_fields_even_when_nothing_else_changed() -> None:
    changes = SellerChanges(
        frozenset({"details"}),
        details=(Detail("description", None), Detail("linkedin", "linkedin.com/company/acme")),
    )

    assert seller_edit_row(changes) == {
        "description": None,
        "linkedin": "linkedin.com/company/acme",
    }


@pytest.mark.parametrize(
    ("signal", "label"),
    [
        ("No Signal", "Unknown"),
        (None, "Unknown"),
        ("Listed on Business-for-Sale Platform", "Interested"),
        ("Expressed Interest Directly / Inbound Deal", "Interested"),
        ("Warm Introduction / Direct Outreach", "Warm intro"),
    ],
)
def test_appetite_signal_maps_to_the_engine_label(signal: str | None, label: str) -> None:
    assert open_to_selling(signal) == label


def test_ranges_are_read_in_millions() -> None:
    assert parse_range("10-40") == parse_range("10-40")
    assert (parse_range("10-").min, parse_range("10-").max) == (10e6, None)
    assert (parse_range("-40").min, parse_range("-40").max) == (None, 40e6)
    assert parse_range(None).is_open


def test_a_bad_range_is_refused() -> None:
    with pytest.raises(ValueError, match="not a range"):
        BuyerFilterQuery.model_validate({"checkSize": "abc"})


def test_url_params_become_typed_filters() -> None:
    filters = BuyerFilterQuery.model_validate(
        {"sector": "Dental,Veterinary", "checkSize": "1-5", "q": "acme"}
    ).to_domain()

    assert filters.sectors == ("Dental", "Veterinary")
    assert filters.check_size.min == 1e6
    assert filters.text == "acme"
    assert filters.narrows


def test_text_search_alone_is_not_a_narrowing_filter() -> None:
    assert not BuyerFilterQuery.model_validate({"q": "acme"}).to_domain().narrows


def test_seller_open_to_selling_is_validated() -> None:
    assert SellerFilterQuery.model_validate(
        {"openToSelling": "Interested"}
    ).to_domain().open_to_selling == ("Interested",)
    with pytest.raises(ValueError, match="unknown open-to-selling"):
        SellerFilterQuery.model_validate({"openToSelling": "Maybe"})


def test_an_empty_update_is_refused_and_a_null_counts_as_sent() -> None:
    with pytest.raises(ValueError, match="at least one field"):
        BuyerUpdate.model_validate({})
    changes = BuyerUpdate.model_validate({"notes": None}).to_domain()
    assert changes.sent == {"notes"}
    assert SellerUpdate.model_validate(
        {"reEngageDate": "2027-01-05"}
    ).to_domain().re_engage_date == date(2027, 1, 5)


def test_a_seller_without_its_own_sector_shows_the_companys() -> None:
    org = Organization(attio_id="o1", name="Omega", domains=["o.com"], sector_focus=["Logistics"])
    role = SellerRoleRow(
        org_attio_id="o1", sector=[], updated_at=datetime(2026, 11, 16, tzinfo=UTC)
    )

    assert to_seller(role, org, {}).sector == "Logistics"
    assert to_seller(role, org, {}).own_sector is None
    assert to_seller(role, org, {}).company_sector == "Logistics"

    role.sector = ["Dental", "Retail"]
    assert to_seller(role, org, {}).sector == "Dental, Retail"
    assert to_seller(role, org, {}).own_sector == "Dental, Retail"
    assert to_seller(role, org, {}).company_sector == "Logistics"

    role.sector, org.sector_focus = [], []
    assert to_seller(role, org, {}).sector is None


def test_a_buyer_keeps_its_company_sector_apart_from_its_target_vertical() -> None:
    org = Organization(attio_id="o1", name="Alpha", domains=["a.com"], sector_focus=["Logistics"])
    role = BuyerRoleRow(
        org_attio_id="o1",
        target_vertical="Dental",
        target_region=[],
        target_country=[],
        updated_at=datetime(2026, 11, 16, tzinfo=UTC),
    )

    buyer = to_buyer(role, org)

    assert (buyer.sectors, buyer.company_sector) == (("Dental",), "Logistics")


def test_hq_and_the_exact_appetite_signal_reach_the_edit_rows() -> None:
    assert buyer_edit_row(BuyerChanges(frozenset({"hq"}), hq="Qatar")) == {"hq_country": "Qatar"}
    assert seller_edit_row(
        SellerChanges(
            frozenset({"hq", "appetite_signal", "open_to_selling"}),
            hq="Qatar",
            open_to_selling="Interested",
            appetite_signal="Listed on Business-for-Sale Platform",
        )
    ) == {"appetite_signal": "Listed on Business-for-Sale Platform", "hq_country": "Qatar"}


def test_an_appetite_signal_is_not_a_group_label_when_the_exact_one_is_sent() -> None:
    seller = NewSeller(
        name="Acme",
        website="acme.com",
        sector="Retail",
        open_to_selling="Interested",
        appetite_signal="Listed on Business-for-Sale Platform",
    )

    assert seller_add_row(seller)["appetite_signal"] == "Listed on Business-for-Sale Platform"
