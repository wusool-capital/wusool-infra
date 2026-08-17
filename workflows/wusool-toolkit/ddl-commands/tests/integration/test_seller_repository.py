from sqlalchemy.ext.asyncio import AsyncSession

from ddl_commands.modules.sellers.infrastructure.models import SellerRole
from ddl_commands.modules.sellers.infrastructure.repositories import SellerRepository
from ddl_commands.shared.database.models import Organization


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


async def test_update_applies_fields(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _seller(db_session, throwaway_org, outreach_tier="cold")

    repo = SellerRepository(db_session)
    updated = await repo.update(str(role.id), outreach_tier="warm")

    assert updated is not None
    assert updated.outreach_tier == "warm"


async def test_get_by_org_attio_id_finds_existing_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _seller(db_session, throwaway_org, outreach_tier="cold")

    repo = SellerRepository(db_session)
    found = await repo.get_by_org_attio_id(throwaway_org.attio_id)

    assert found is not None
    assert found.id == role.id


async def test_get_by_org_attio_id_returns_none_when_no_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    repo = SellerRepository(db_session)
    found = await repo.get_by_org_attio_id(throwaway_org.attio_id)
    assert found is None


async def test_create_inserts_a_new_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    repo = SellerRepository(db_session)
    created = await repo.create(throwaway_org.attio_id, outreach_tier="Tier 1")

    assert created.org_attio_id == throwaway_org.attio_id
    assert created.outreach_tier == "Tier 1"
