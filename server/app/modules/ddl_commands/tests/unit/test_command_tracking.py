"""`track_command` records how a write ended, and never fails the write itself."""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

import app.modules.ddl_commands.api.command_tracking as tracking
from app.modules.activities import ActorType
from app.modules.ddl_commands.api.write_errors import PartialWriteError


@pytest.fixture
def service(monkeypatch):
    calls = SimpleNamespace(started=[], finished=[], start_error=None, finish_error=None)

    async def start_command_run(**kwargs):
        if calls.start_error:
            raise calls.start_error
        calls.started.append(kwargs)
        return uuid.uuid4()

    async def finish_command_run(run_id, **kwargs):
        if calls.finish_error:
            raise calls.finish_error
        calls.finished.append({"run_id": run_id, **kwargs})

    monkeypatch.setattr(
        tracking,
        "ddl_commands_service",
        lambda: SimpleNamespace(
            start_command_run=start_command_run, finish_command_run=finish_command_run
        ),
    )
    return calls


async def test_a_clean_write_finishes_succeeded_with_what_the_body_reported(service) -> None:
    org_id = "org-1"
    async with tracking.track_command("add_buyer", invoked_via="slack", requested_by="U1") as run:
        run.org_attio_id = org_id
        run.changed_fields = ["model"]

    (finished,) = service.finished
    assert finished["status"] == "succeeded"
    assert finished["org_attio_id"] == org_id
    assert finished["changed_fields"] == ["model"]
    assert finished["run_id"] == run.run_id
    assert run.context.command_run_id == run.run_id
    assert run.context.actor.type is ActorType.SLACK_USER


async def test_a_partial_write_is_recorded_with_what_landed_and_reraised(service) -> None:
    with pytest.raises(PartialWriteError):
        async with tracking.track_command("edit_seller", invoked_via="slack", requested_by="U1"):
            raise PartialWriteError(["organization fields (Attio)"], RuntimeError("db down"))

    (finished,) = service.finished
    assert finished["status"] == "partial"
    assert finished["landed"] == ["organization fields (Attio)"]
    assert finished["error"] == "RuntimeError: db down"


async def test_a_write_that_fails_before_anything_landed_is_failed_not_partial(service) -> None:
    with pytest.raises(PartialWriteError):
        async with tracking.track_command("edit_seller", invoked_via="slack", requested_by="U1"):
            raise PartialWriteError([], RuntimeError("attio down"))

    assert service.finished[0]["status"] == "failed"


async def test_an_expected_error_is_recorded_failed_and_reraised(service) -> None:
    with pytest.raises(LookupError):
        async with tracking.track_command("add_buyer", invoked_via="slack", requested_by="U1"):
            raise LookupError("already exists")

    assert service.finished[0]["status"] == "failed"
    assert service.finished[0]["error"] == "LookupError: already exists"


async def test_a_discovery_run_has_a_system_actor_and_no_requester(service) -> None:
    async with tracking.track_command(
        "add_seller", invoked_via="discovery", requested_by=None
    ) as run:
        pass

    assert run.context.actor.type is ActorType.SYSTEM
    assert run.context.actor.ref == "discovery"
    assert service.started[0]["requested_by"] is None


async def test_a_failing_ledger_never_fails_the_write(service) -> None:
    service.start_error = RuntimeError("ledger down")
    service.finish_error = RuntimeError("ledger down")

    async with tracking.track_command("add_buyer", invoked_via="slack", requested_by="U1") as run:
        pass

    assert run.run_id is None
    assert run.context.command_run_id is None
    assert service.finished == []


async def test_a_cancelled_write_is_recorded_failed_and_still_cancels(service) -> None:
    with pytest.raises(asyncio.CancelledError):
        async with tracking.track_command("edit_buyer", invoked_via="slack", requested_by="U1"):
            raise asyncio.CancelledError

    (finished,) = service.finished
    assert finished["status"] == "failed"
    assert "cancelled" in finished["error"]


async def test_an_expected_error_after_an_attio_write_landed_is_partial(service) -> None:
    """e.g. "already exists" raised after the org and role entry were created in Attio."""
    with pytest.raises(LookupError):
        async with tracking.track_command(
            "add_seller", invoked_via="slack", requested_by="U1"
        ) as run:
            run.landed.append("seller role entry (Attio)")
            raise LookupError("already exists")

    (finished,) = service.finished
    assert finished["status"] == "partial"
    assert finished["landed"] == ["seller role entry (Attio)"]


async def test_a_cancel_after_an_attio_write_landed_is_partial(service) -> None:
    with pytest.raises(asyncio.CancelledError):
        async with tracking.track_command(
            "add_seller", invoked_via="slack", requested_by="U1"
        ) as run:
            run.landed.append("organization created in Attio")
            raise asyncio.CancelledError

    assert service.finished[0]["status"] == "partial"


def test_uuid_or_none() -> None:
    value = uuid.uuid4()
    assert tracking.uuid_or_none(str(value)) == value
    assert tracking.uuid_or_none("not-a-uuid") is None
    assert tracking.uuid_or_none(None) is None
