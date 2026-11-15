"""Adding a seller goes through the same write path as Slack's /add-seller."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.modules.crm.api.schemas import SellerCreate
from app.modules.crm.application.service import CrmService
from app.modules.crm.domain.roles import NewSeller, RoleAlreadyExistsError, SellerFilters
from app.modules.crm.providers.ddl_commands_writer import DdlCommandsRoleWriter, seller_add_row
from app.modules.crm.tests.unit.crm_fakes import JULES, FakeReader, FakeWriter


def test_a_new_seller_row_carries_only_what_was_given() -> None:
    row = seller_add_row(NewSeller(name="Acme", website="acme.com", sector="Clinic"))
    full = seller_add_row(
        NewSeller(
            name="Acme",
            website="acme.com",
            sector="Clinic",
            hq="Japan",
            open_to_selling="Warm intro",
            est_revenue_usd=4e6,
            est_ebitda_usd=1e6,
            re_engage_date=date(2027, 1, 5),
        )
    )

    assert row == {"org_name": "Acme", "domain": "acme.com", "sector_focus": ["Clinic"]}
    assert full["appetite_signal"] == "Warm Introduction / Direct Outreach"
    assert (full["hq_country"], full["est_revenue"], full["re_engage_date"]) == (
        "Japan",
        4e6,
        "2027-01-05",
    )


def test_attio_lists_the_sectors_and_hq_countries_the_form_offers() -> None:
    writer = DdlCommandsRoleWriter()

    assert "Clinic" in writer.seller_sectors()
    assert "Japan" in writer.hq_countries()


def test_a_seller_create_refuses_ebitda_above_revenue() -> None:
    with pytest.raises(ValidationError, match="EBITDA is above revenue"):
        SellerCreate.model_validate(
            {
                "name": "A",
                "website": "a.com",
                "sector": "Clinic",
                "estRevenueUsd": 1,
                "estEbitdaUsd": 2,
            }
        )


async def test_a_new_seller_is_added_and_read_back() -> None:
    reader = FakeReader()
    service = CrmService(reader, FakeWriter(reader))

    role = await service.add_seller(
        JULES, NewSeller(name="Fresh Co", website="fresh.com", sector="Clinic")
    )

    assert (role.id, role.name) == ("s2", "Fresh Co")


async def test_a_seller_with_a_known_domain_is_refused() -> None:
    reader = FakeReader()
    service = CrmService(reader, FakeWriter(reader, add_outcome="existing"))

    with pytest.raises(RoleAlreadyExistsError) as raised:
        await service.add_seller(
            JULES, NewSeller(name="Fresh Co", website="fresh.com", sector="Clinic")
        )

    assert raised.value.kind == "seller"


async def test_the_first_sellers_page_lists_the_add_form_choices() -> None:
    reader = FakeReader()
    service = CrmService(reader, FakeWriter(reader))

    page = await service.sellers(SellerFilters(), None, 10)

    assert page.options.sector_choices == ("Clinic", "Garage")
    assert "Japan" in page.options.hq_countries
