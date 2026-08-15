from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sellers.infrastructure.models import SellerRole
from app.modules.sellers.infrastructure.repositories import SellerRepository
from app.shared.database.models import Organization


async def _seller(db_session: AsyncSession, org: Organization, **fields) -> SellerRole:
    role = SellerRole(org_attio_id=org.attio_id, **fields)
    db_session.add(role)
    await db_session.flush()
    return role


async def test_search_by_organization_name_finds_typo_tolerant_match(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.name = "Acme Capital Partners"
    await _seller(db_session, throwaway_org)

    repo = SellerRepository(db_session)
    results = await repo.search_by_organization_name("Acme Captial")  # typo, deliberate
    assert any(r.org_attio_id == throwaway_org.attio_id for r in results)


async def test_search_excludes_archived_by_default_but_finds_with_include_archived(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    from datetime import UTC, datetime

    throwaway_org.name = "Archived Target Co"
    await _seller(db_session, throwaway_org, archived_at=datetime.now(UTC))

    repo = SellerRepository(db_session)
    default_results = await repo.search_by_organization_name("Archived Target Co")
    assert not any(r.org_attio_id == throwaway_org.attio_id for r in default_results)

    with_archived = await repo.search_by_organization_name(
        "Archived Target Co", include_archived=True
    )
    assert any(r.org_attio_id == throwaway_org.attio_id for r in with_archived)


async def test_get_eligible_sellers_excludes_archived(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    from datetime import UTC, datetime

    throwaway_org.name = "Eligible Filter Test Co"
    await _seller(db_session, throwaway_org, archived_at=datetime.now(UTC))

    repo = SellerRepository(db_session)
    eligible = await repo.get_eligible_sellers(limit=1000)
    assert not any(r.org_attio_id == throwaway_org.attio_id for r in eligible)


async def test_update_sets_bot_managed_fields(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _seller(db_session, throwaway_org, outreach_tier="cold")

    repo = SellerRepository(db_session)
    updated = await repo.update(str(role.id), "U123", outreach_tier="warm")

    assert updated is not None
    assert updated.outreach_tier == "warm"
    assert updated.bot_managed_at is not None
    assert updated.bot_managed_by == "U123"


async def test_archive_sets_archived_at_and_bot_managed_fields(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _seller(db_session, throwaway_org)

    repo = SellerRepository(db_session)
    archived = await repo.archive(str(role.id), "U123")

    assert archived is not None
    assert archived.archived_at is not None
    assert archived.bot_managed_at is not None
    assert archived.bot_managed_by == "U123"
