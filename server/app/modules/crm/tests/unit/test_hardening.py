"""Write-body validation, Attio-owned option lists, and the typed money read."""

import pytest
from pydantic import ValidationError

from app.modules import ddl_commands
from app.modules.crm.api.schemas import BuyerCreate, BuyerUpdate, SellerUpdate
from app.modules.crm.application.service import CrmService
from app.modules.crm.domain.roles import BuyerFilters, appetite_signals
from app.modules.crm.persistence.mappers import amount
from app.modules.crm.providers.ddl_commands_writer import DdlCommandsRoleWriter
from app.modules.crm.tests.unit.crm_fakes import FakeReader, FakeWriter


@pytest.mark.parametrize(
    "body",
    [
        '{"checkSizeMinUsd": -1}',
        '{"ebitdaFloorUsd": NaN}',
        '{"checkSizeMaxUsd": Infinity}',
        '{"checkSizeMinUsd": 50000000, "checkSizeMaxUsd": 10000000}',
    ],
)
def test_buyer_updates_refuse_bad_money(body: str) -> None:
    with pytest.raises(ValidationError):
        BuyerUpdate.model_validate_json(body)


def test_a_new_buyer_cannot_have_its_check_size_backwards() -> None:
    with pytest.raises(ValidationError, match="check size from"):
        BuyerCreate.model_validate(
            {
                "name": "A",
                "website": "a.com",
                "sector": "Dental",
                "checkSizeMinUsd": 9,
                "checkSizeMaxUsd": 1,
            }
        )


def test_a_seller_update_refuses_ebitda_above_revenue_and_a_cleared_appetite() -> None:
    with pytest.raises(ValidationError, match="EBITDA is above revenue"):
        SellerUpdate.model_validate({"estRevenueUsd": 1, "estEbitdaUsd": 2})
    with pytest.raises(ValidationError, match="cannot be cleared"):
        SellerUpdate.model_validate({"openToSelling": None})
    assert SellerUpdate.model_validate({"estEbitdaUsd": None}).to_domain().sent == {
        "est_ebitda_usd"
    }


def test_the_appetite_signals_we_map_are_attio_options() -> None:
    """The grouping repeats Attio's option text, so a rename in `ddl_commands` must fail here."""
    options = next(
        column.spec.options
        for column in ddl_commands.columns_for("seller")
        if column.field == "appetite_signal" and column.spec is not None
    )
    mapped = {
        signal
        for label in ("Unknown", "Interested", "Warm intro")
        for signal in appetite_signals(label)
    }  # type: ignore[arg-type]

    assert mapped == set(options or ())


def test_buyer_statuses_are_attios_allowed_options() -> None:
    assert DdlCommandsRoleWriter().buyer_statuses() == ("Active", "Paused", "Completed", "Dormant")


async def test_only_the_first_page_gets_the_attio_statuses() -> None:
    reader = FakeReader()
    service = CrmService(reader, FakeWriter(reader))

    first = await service.buyers(BuyerFilters(), None, 10)
    later = await service.buyers(BuyerFilters(), "cursor", 10)

    assert first.options.statuses == ("Active", "Dormant")
    assert later.options.statuses == ("Active",)


@pytest.mark.parametrize(
    ("blob", "expected"),
    [
        ({"amount": 5, "currency": "USD"}, 5.0),
        ({"amount": 2.5}, 2.5),
        ({"amount": True}, None),
        ({"amount": "7"}, None),
        ({"currency": "USD"}, None),
        ({}, None),
        (None, None),
    ],
)
def test_the_money_blob_reads_numbers_only(blob, expected) -> None:  # noqa: ANN001
    assert amount(blob) == expected
