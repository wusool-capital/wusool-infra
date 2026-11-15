"""A buyer's geography is one list in the Engine and two fields in Attio."""

import pytest

from app.modules.crm.application.service import CrmService
from app.modules.crm.domain.roles import (
    BuyerChanges,
    BuyerFilters,
    InvalidRoleFieldsError,
    NewBuyer,
    split_geographies,
)
from app.modules.crm.providers.ddl_commands_writer import buyer_add_row, buyer_edit_row
from app.modules.crm.tests.unit.crm_fakes import JULES, FakeReader, FakeWriter

_REGIONS = ("GCC", "Europe")
_COUNTRIES = ("Qatar", "Oman")


def _service() -> tuple[CrmService, FakeWriter]:
    reader = FakeReader()
    writer = FakeWriter(reader)
    return CrmService(reader, writer), writer


def test_picks_are_sorted_into_regions_and_countries() -> None:
    split = split_geographies(["Qatar", "GCC", "Atlantis", "Oman"], _REGIONS, _COUNTRIES)

    assert (split.regions, split.countries, split.unknown) == (
        ("GCC",),
        ("Qatar", "Oman"),
        ("Atlantis",),
    )


def test_a_geography_edit_sends_only_the_groups_that_have_a_pick() -> None:
    both = buyer_edit_row(
        BuyerChanges(frozenset({"geographies"}), geographies=("GCC", "Qatar")), _REGIONS, _COUNTRIES
    )
    only_countries = buyer_edit_row(
        BuyerChanges(frozenset({"geographies"}), geographies=("Oman",)), _REGIONS, _COUNTRIES
    )

    assert both == {"target_region": ["GCC"], "target_country": ["Qatar"]}
    assert only_countries == {"target_country": ["Oman"]}


def test_other_edits_leave_geography_alone() -> None:
    row = buyer_edit_row(BuyerChanges(frozenset({"notes"}), notes="x"), _REGIONS, _COUNTRIES)

    assert row == {"notes": "x"}


def test_a_new_buyer_carries_its_geography_into_the_row() -> None:
    row = buyer_add_row(
        NewBuyer(name="A", website="a.com", sector="Dental", geographies=("Europe", "Qatar")),
        _REGIONS,
        _COUNTRIES,
    )

    assert (row["target_region"], row["target_country"]) == (["Europe"], ["Qatar"])


async def test_a_valid_swap_of_region_and_added_country_is_written() -> None:
    service, writer = _service()

    await service.edit_buyer(
        JULES,
        "b1",
        BuyerChanges(frozenset({"geographies"}), geographies=("Europe", "Qatar")),
        '"v1"',
    )

    assert writer.changes[0].geographies == ("Europe", "Qatar")


@pytest.mark.parametrize(
    ("picked", "message"),
    [
        (("Atlantis",), "Atlantis is not a region or country"),
        # The sample buyer holds the region GCC, and Attio cannot empty a group.
        (("Qatar",), "Keep at least one region"),
    ],
)
async def test_a_bad_geography_is_refused_before_anything_is_written(
    picked: tuple[str, ...], message: str
) -> None:
    service, writer = _service()

    with pytest.raises(InvalidRoleFieldsError, match=message):
        await service.edit_buyer(
            JULES, "b1", BuyerChanges(frozenset({"geographies"}), geographies=picked), '"v1"'
        )

    assert writer.changes == []


async def test_a_new_buyer_with_an_unknown_geography_is_refused() -> None:
    service, _ = _service()

    with pytest.raises(InvalidRoleFieldsError, match="Atlantis"):
        await service.add_buyer(
            JULES, NewBuyer(name="A", website="a.com", sector="Dental", geographies=("Atlantis",))
        )


async def test_the_first_page_lists_everything_attio_allows() -> None:
    service, _ = _service()

    page = await service.buyers(BuyerFilters(), None, 10)

    assert (page.options.regions, page.options.countries) == (_REGIONS, _COUNTRIES)
