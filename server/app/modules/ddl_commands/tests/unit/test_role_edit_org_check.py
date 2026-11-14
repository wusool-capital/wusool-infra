"""The headless edits are callable without Slack, so they must not trust the
caller to pair the role with its own organization.
"""

import uuid
from types import SimpleNamespace

import pytest

import app.modules.ddl_commands.api.buyer_edit as buyer_edit_module
import app.modules.ddl_commands.api.command_tracking as tracking
import app.modules.ddl_commands.api.seller_edit as seller_edit_module
from app.modules.ddl_commands.api.write_errors import OrgMismatchError, OrgRemovedError


def _edit(kind: str, *, org_attio_id: str):
    if kind == "buyer":
        return buyer_edit_module.write_buyer_edit(
            buyer_role_id=str(uuid.uuid4()),
            org_attio_id=org_attio_id,
            org_extracted={"name": "Renamed"},
            role_extracted={},
            requested_by=None,
        )
    return seller_edit_module.write_seller_edit(
        seller_role_id=str(uuid.uuid4()),
        org_attio_id=org_attio_id,
        org_extracted={"name": "Renamed"},
        role_extracted={},
        requested_by=None,
    )


@pytest.fixture
def finished(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    async def start_command_run(**_kwargs):
        return uuid.uuid4()

    async def finish_command_run(_run_id, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        tracking,
        "ddl_commands_service",
        lambda: SimpleNamespace(
            start_command_run=start_command_run, finish_command_run=finish_command_run
        ),
    )
    return calls


def _load_role(monkeypatch, *, removed_at=None) -> None:
    async def resolve(_role_id):
        return SimpleNamespace(
            organization=SimpleNamespace(attio_id="org-a", removed_at=removed_at),
            legacy_entry_id=None,
        )

    def no_attio():
        raise AssertionError("Attio must not be reached")

    monkeypatch.setattr(buyer_edit_module, "resolve_buyer_by_id", resolve)
    monkeypatch.setattr(seller_edit_module, "resolve_seller_by_id", resolve)
    monkeypatch.setattr(buyer_edit_module, "get_attio_client", no_attio)
    monkeypatch.setattr(seller_edit_module, "get_attio_client", no_attio)


@pytest.mark.parametrize("kind", ["buyer", "seller"])
async def test_an_org_that_is_not_the_roles_is_refused_before_attio(
    monkeypatch, finished, kind
) -> None:
    _load_role(monkeypatch)

    with pytest.raises(OrgMismatchError):
        await _edit(kind, org_attio_id="org-b")

    assert finished[0]["status"] == "failed"


@pytest.mark.parametrize("kind", ["buyer", "seller"])
async def test_a_removed_org_is_refused_before_attio(monkeypatch, finished, kind) -> None:
    _load_role(monkeypatch, removed_at="2026-11-01")

    with pytest.raises(OrgRemovedError):
        await _edit(kind, org_attio_id="org-a")

    assert finished[0]["status"] == "failed"
