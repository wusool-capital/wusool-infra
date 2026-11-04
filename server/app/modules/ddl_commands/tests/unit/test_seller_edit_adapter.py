"""Saving web research through `/edit-seller`'s write: only into fields still
empty, only valid values, and with what landed reported on a partial write."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.providers.matching_engine import seller_edit_adapter
from app.modules.ddl_commands.providers.matching_engine.seller_edit_adapter import (
    DdlCommandsSellerEditAdapter,
)
from app.modules.matching_engine import SellerEditOutcome, SellerFieldEdit


def _seller(**org_values: object) -> SimpleNamespace:
    org = SimpleNamespace(attio_id="org-1", removed_at=None, facebook=None, sector_focus=None)
    for name, value in org_values.items():
        setattr(org, name, value)
    return SimpleNamespace(organization=org, est_revenue=None)


@pytest.fixture
def write(monkeypatch):
    write = AsyncMock()
    monkeypatch.setattr(seller_edit_adapter, "write_seller_edit", write)
    return write


def _resolve(monkeypatch, seller: SimpleNamespace | None) -> None:
    monkeypatch.setattr(seller_edit_adapter, "resolve_seller_by_id", AsyncMock(return_value=seller))


async def _apply(*edits: SellerFieldEdit):
    return await DdlCommandsSellerEditAdapter().apply(
        seller_role_id="role-1", edits=edits, requested_by="U1"
    )


async def test_saves_empty_fields_through_the_edit_write(monkeypatch, write) -> None:
    _resolve(monkeypatch, _seller())

    result = await _apply(
        SellerFieldEdit("facebook", "organization", "https://facebook.com/sun"),
        SellerFieldEdit("est_revenue", "seller_role", 2_000_000),
    )

    assert result.outcome is SellerEditOutcome.SAVED
    kwargs = write.await_args.kwargs
    assert kwargs["org_attio_id"] == "org-1"
    assert kwargs["org_extracted"] == {"facebook": "https://facebook.com/sun"}
    assert set(kwargs["role_extracted"]) == {"est_revenue"}
    assert kwargs["requested_by"] == "U1"


async def test_a_field_filled_in_since_is_a_conflict_and_nothing_is_written(
    monkeypatch, write
) -> None:
    _resolve(monkeypatch, _seller(facebook="https://facebook.com/someone-else"))

    result = await _apply(SellerFieldEdit("facebook", "organization", "https://facebook.com/sun"))

    assert result.outcome is SellerEditOutcome.CONFLICT
    assert result.conflicts == ("facebook",)
    write.assert_not_awaited()


async def test_a_value_outside_the_vocabulary_is_refused(monkeypatch, write) -> None:
    _resolve(monkeypatch, _seller())

    result = await _apply(SellerFieldEdit("sector_focus", "organization", ["Not A Sector"]))

    assert result.outcome is SellerEditOutcome.INVALID
    write.assert_not_awaited()


async def test_an_unknown_field_is_refused(monkeypatch, write) -> None:
    _resolve(monkeypatch, _seller())

    result = await _apply(SellerFieldEdit("made_up", "seller_role", "x"))

    assert result.outcome is SellerEditOutcome.INVALID
    write.assert_not_awaited()


async def test_a_removed_seller_is_not_found(monkeypatch, write) -> None:
    _resolve(monkeypatch, None)

    result = await _apply(SellerFieldEdit("facebook", "organization", "https://f"))

    assert result.outcome is SellerEditOutcome.NOT_FOUND


async def test_a_partial_write_reports_what_landed(monkeypatch, write) -> None:
    _resolve(monkeypatch, _seller())
    write.side_effect = PartialWriteError(["organization fields (Attio)"], RuntimeError("db down"))

    result = await _apply(SellerFieldEdit("facebook", "organization", "https://f"))

    assert result.outcome is SellerEditOutcome.PARTIAL
    assert result.landed == ("organization fields (Attio)",)
    assert result.message == "db down"
