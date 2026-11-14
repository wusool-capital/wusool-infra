"""`write_buyer_edit` is callable without Slack, so it must not trust the
caller to pair the buyer with its own organization.
"""

import uuid
from types import SimpleNamespace

import pytest

import app.modules.ddl_commands.api.buyer_edit as buyer_edit_module
import app.modules.ddl_commands.api.command_tracking as tracking


async def test_an_org_that_is_not_the_buyers_is_refused_before_attio(monkeypatch) -> None:
    finished: list[dict] = []

    async def start_command_run(**_kwargs):
        return uuid.uuid4()

    async def finish_command_run(_run_id, **kwargs):
        finished.append(kwargs)

    async def resolve_buyer(_buyer_role_id):
        return SimpleNamespace(
            organization=SimpleNamespace(attio_id="org-a", removed_at=None),
            legacy_entry_id=None,
        )

    def no_attio():
        raise AssertionError("Attio must not be reached")

    monkeypatch.setattr(
        tracking,
        "ddl_commands_service",
        lambda: SimpleNamespace(
            start_command_run=start_command_run, finish_command_run=finish_command_run
        ),
    )
    monkeypatch.setattr(buyer_edit_module, "resolve_buyer_by_id", resolve_buyer)
    monkeypatch.setattr(buyer_edit_module, "get_attio_client", no_attio)

    with pytest.raises(buyer_edit_module.OrgMismatchError):
        await buyer_edit_module.write_buyer_edit(
            buyer_role_id=str(uuid.uuid4()),
            org_attio_id="org-b",
            org_extracted={"name": "Renamed"},
            role_extracted={},
            requested_by=None,
        )

    assert finished[0]["status"] == "failed"
