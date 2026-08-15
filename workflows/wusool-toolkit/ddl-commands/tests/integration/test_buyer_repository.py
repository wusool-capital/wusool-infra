from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.buyers.infrastructure.models import BuyerRole
from app.modules.buyers.infrastructure.repositories import BuyerRepository
from app.shared.database.models import Organization


async def _buyer(db_session: AsyncSession, org: Organization, **fields) -> BuyerRole:
    role = BuyerRole(org_attio_id=org.attio_id, **fields)
    db_session.add(role)
    await db_session.flush()
    return role


async def test_search_by_organization_name_finds_typo_tolerant_match(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.name = "Blue Horizon Buyers"
    await _buyer(db_session, throwaway_org)

    repo = BuyerRepository(db_session)
    results = await repo.search_by_organization_name("Blue Horizen Buyers")  # typo, deliberate
    assert any(r.org_attio_id == throwaway_org.attio_id for r in results)


async def test_search_excludes_archived_by_default_but_finds_with_include_archived(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    from datetime import UTC, datetime

    throwaway_org.name = "Archived Buyer Co"
    await _buyer(db_session, throwaway_org, archived_at=datetime.now(UTC))

    repo = BuyerRepository(db_session)
    default_results = await repo.search_by_organization_name("Archived Buyer Co")
    assert not any(r.org_attio_id == throwaway_org.attio_id for r in default_results)

    with_archived = await repo.search_by_organization_name(
        "Archived Buyer Co", include_archived=True
    )
    assert any(r.org_attio_id == throwaway_org.attio_id for r in with_archived)


async def test_update_sets_bot_managed_fields(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _buyer(db_session, throwaway_org, model="Buy-and-build")

    repo = BuyerRepository(db_session)
    updated = await repo.update(str(role.id), "U123", model="Roll-up")

    assert updated is not None
    assert updated.model == "Roll-up"
    assert updated.bot_managed_at is not None
    assert updated.bot_managed_by == "U123"


async def test_archive_sets_archived_at_and_bot_managed_fields(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _buyer(db_session, throwaway_org)

    repo = BuyerRepository(db_session)
    archived = await repo.archive(str(role.id), "U123")

    assert archived is not None
    assert archived.archived_at is not None
    assert archived.bot_managed_at is not None
    assert archived.bot_managed_by == "U123"
