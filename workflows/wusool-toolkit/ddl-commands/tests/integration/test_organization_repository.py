import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ddl_commands.shared.database.models import Organization
from ddl_commands.shared.database.organization_repository import OrganizationRepository


async def test_get_by_id_returns_the_row(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    repo = OrganizationRepository(db_session)
    found = await repo.get_by_id(throwaway_org.attio_id)
    assert found is not None
    assert found.attio_id == throwaway_org.attio_id


async def test_get_by_id_returns_none_for_missing_org(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)
    found = await repo.get_by_id(f"nonexistent-{uuid.uuid4()}")
    assert found is None


async def test_update_applies_fields(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    repo = OrganizationRepository(db_session)
    updated = await repo.update(
        throwaway_org.attio_id, description="Updated description", client_type="Buy-Side"
    )

    assert updated is not None
    assert updated.description == "Updated description"
    assert updated.client_type == "Buy-Side"


async def test_update_returns_none_for_missing_org(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)
    updated = await repo.update(f"nonexistent-{uuid.uuid4()}", description="x")
    assert updated is None


async def test_search_by_name_finds_typo_tolerant_match(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.name = "Zephyr Manufacturing Co"
    await db_session.flush()

    repo = OrganizationRepository(db_session)
    results = await repo.search_by_name("Zephir Manufacturing")  # typo, deliberate
    assert any(o.attio_id == throwaway_org.attio_id for o in results)


async def test_search_by_name_no_match_returns_empty(db_session: AsyncSession) -> None:
    repo = OrganizationRepository(db_session)
    results = await repo.search_by_name(f"totally-unrelated-{uuid.uuid4()}")
    assert results == []


async def test_get_by_id_with_roles_eager_loads_seller_and_buyer_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    repo = OrganizationRepository(db_session)
    found = await repo.get_by_id_with_roles(throwaway_org.attio_id)
    assert found is not None
    # No lazy-load error accessing these outside further awaits — proves
    # they were eager-loaded, not just present on the still-open session.
    assert found.seller_role is None
    assert found.buyer_role is None


async def test_create_inserts_a_new_organization(db_session: AsyncSession) -> None:
    attio_id = f"test-org-{uuid.uuid4()}"
    repo = OrganizationRepository(db_session)

    created = await repo.create(attio_id, "Brand New Co", hq_country="AE")

    assert created.attio_id == attio_id
    assert created.name == "Brand New Co"
    assert created.hq_country == "AE"

    found = await repo.get_by_id(attio_id)
    assert found is not None
    assert found.name == "Brand New Co"
