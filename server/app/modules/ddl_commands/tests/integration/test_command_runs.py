"""`command_runs` ledger and the activities seller/buyer writes record."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import BuyerRole, Organization, SellerRole
from app.modules.activities import ActivityActor, ActivitySource
from app.modules.ddl_commands.application.buyers import BuyerService
from app.modules.ddl_commands.application.command_runs import CommandRunService
from app.modules.ddl_commands.application.ports.unit_of_work import DdlCommandsUnitOfWorkFactory
from app.modules.ddl_commands.application.sellers import SellerService
from app.modules.ddl_commands.application.write_context import WriteContext
from app.modules.ddl_commands.persistence.unit_of_work import SqlAlchemyDdlCommandsUnitOfWork


def _uow_factory(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> DdlCommandsUnitOfWorkFactory:
    return lambda: SqlAlchemyDdlCommandsUnitOfWork(db_sessionmaker)


async def _run_row(db_sessionmaker: async_sessionmaker[AsyncSession], run_id: uuid.UUID):
    async with db_sessionmaker() as session:
        return (
            await session.execute(text("SELECT * FROM command_runs WHERE id = :id"), {"id": run_id})
        ).one()


async def _activities(db_sessionmaker: async_sessionmaker[AsyncSession], where: str, **params):
    async with db_sessionmaker() as session:
        return (
            await session.execute(
                text(
                    "SELECT event_type, actor_type, actor_ref, source, outcome, payload, "
                    "ledger_type, ledger_id, subject_uuid, subject_attio_id "
                    f"FROM activities WHERE {where}"
                ),
                params,
            )
        ).all()


async def test_a_run_is_started_then_finished(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    service = CommandRunService(_uow_factory(db_sessionmaker))

    run_id = await service.start_command_run(
        command="edit_seller", invoked_via="slack", requested_by="U123"
    )
    started = await _run_row(db_sessionmaker, run_id)
    assert (started.status, started.requested_by, started.finished_at) == ("running", "U123", None)

    await service.finish_command_run(
        run_id,
        status="partial",
        landed=["organization fields (Attio)"],
        changed_fields=["name"],
        error="RuntimeError: boom",
    )
    finished = await _run_row(db_sessionmaker, run_id)
    assert finished.status == "partial"
    assert finished.landed == ["organization fields (Attio)"]
    assert finished.changed_fields == ["name"]
    assert finished.error == "RuntimeError: boom"
    assert finished.finished_at is not None


async def test_subject_ids_with_no_postgres_row_become_null_not_an_fk_error(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    service = CommandRunService(_uow_factory(db_sessionmaker))

    run_id = await service.start_command_run(
        command="add_seller",
        invoked_via="discovery",
        requested_by=None,
        org_attio_id=f"never-mirrored-{uuid.uuid4()}",
        seller_role_id=uuid.uuid4(),
    )
    await service.finish_command_run(
        run_id,
        status="failed",
        org_attio_id=f"never-mirrored-{uuid.uuid4()}",
        buyer_role_id=uuid.uuid4(),
    )

    row = await _run_row(db_sessionmaker, run_id)
    assert (row.org_attio_id, row.seller_role_id, row.buyer_role_id) == (None, None, None)


async def test_finish_links_the_org_and_role_that_now_exist(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="Linked Co"))
        await session.flush()
        role = SellerRole(org_attio_id=org_id)
        session.add(role)
        await session.flush()
        role_id = role.id
        await session.commit()
    service = CommandRunService(_uow_factory(db_sessionmaker))
    run_id = await service.start_command_run(
        command="add_seller", invoked_via="slack", requested_by="U1"
    )

    await service.finish_command_run(
        run_id, status="succeeded", org_attio_id=org_id, seller_role_id=role_id
    )

    row = await _run_row(db_sessionmaker, run_id)
    assert (row.org_attio_id, row.seller_role_id) == (org_id, role_id)


async def test_create_seller_records_one_added_activity_linked_to_the_run(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    runs = CommandRunService(_uow_factory(db_sessionmaker))
    run_id = await runs.start_command_run(
        command="add_seller", invoked_via="slack", requested_by="U123"
    )
    context = WriteContext(ActivityActor.slack("U123"), ActivitySource.SLACK, run_id)
    org_id = f"test-org-{uuid.uuid4()}"
    entry_id = f"entry-{uuid.uuid4()}"

    async def create() -> SellerRole:
        return await SellerService(_uow_factory(db_sessionmaker)).create_seller(
            org_attio_id=org_id,
            entry_id=entry_id,
            is_new_org=True,
            context=context,
            org_name="Added Co",
            role_fields={"outreach_tier": "cold"},
        )

    role = await create()
    await create()  # an exact retry must not add a second row

    (row,) = await _activities(db_sessionmaker, "ledger_id = :id", id=run_id)
    assert row.event_type == "seller.added"
    assert (row.ledger_type, row.ledger_id) == ("command_run", run_id)
    assert (row.actor_type, row.actor_ref, row.source) == ("slack_user", "U123", "slack")
    assert row.outcome == "succeeded"
    assert row.subject_uuid == role.id
    assert row.subject_attio_id == entry_id
    assert row.payload == {
        "kind": "profile_write",
        "changed_fields": ["outreach_tier"],
        "is_new_org": True,
    }


async def test_update_buyer_records_the_changed_field_names_not_their_values(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="Edit Co"))
        await session.flush()
        role = BuyerRole(org_attio_id=org_id, model="Strategic", legacy_entry_id="entry-b1")
        session.add(role)
        await session.flush()
        role_id = role.id
        await session.commit()

    await BuyerService(_uow_factory(db_sessionmaker)).update_buyer(
        str(role_id),
        {"model": "Roll-up secret value"},
        context=WriteContext(ActivityActor.slack("U9"), ActivitySource.SLACK),
        org_attio_id=org_id,
        org_fields={"name": "Renamed Co"},
    )

    (row,) = await _activities(db_sessionmaker, "subject_uuid = :id", id=role_id)
    assert row.event_type == "buyer.edited"
    assert row.payload == {
        "kind": "profile_write",
        "changed_fields": ["model", "name"],
        "is_new_org": False,
    }
    assert "secret" not in str(row.payload)
    assert (row.ledger_type, row.ledger_id) == (None, None)


async def test_an_edit_that_changes_nothing_records_no_event(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="No-op Co"))
        await session.flush()
        role = SellerRole(org_attio_id=org_id, legacy_entry_id="entry-s1")
        session.add(role)
        await session.flush()
        role_id = role.id
        await session.commit()

    await SellerService(_uow_factory(db_sessionmaker)).update_seller(
        str(role_id),
        {},
        context=WriteContext(ActivityActor.slack("U9"), ActivitySource.SLACK),
        org_attio_id=org_id,
        org_fields={},
    )

    assert await _activities(db_sessionmaker, "subject_uuid = :id", id=role_id) == []
