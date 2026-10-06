import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization
from app.modules.organizations import OrganizationRepository


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


async def test_update_applies_fields(db_session: AsyncSession, throwaway_org: Organization) -> None:
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


async def test_search_by_name_excludes_removed_org(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    from datetime import UTC, datetime

    throwaway_org.name = "Zephyr Manufacturing Co"
    throwaway_org.removed_at = datetime.now(UTC)
    await db_session.flush()

    repo = OrganizationRepository(db_session)
    results = await repo.search_by_name("Zephyr Manufacturing")
    assert all(o.attio_id != throwaway_org.attio_id for o in results)


async def test_get_by_id_with_roles_eager_loads_seller_and_buyer_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    repo = OrganizationRepository(db_session)
    found = await repo.get_by_id_with_roles(throwaway_org.attio_id)
    assert found is not None
    # No lazy-load error accessing these outside further awaits — proves
    # they were eager-loaded, not just present on the still-open session.
    assert found.seller_roles == []
    assert found.buyer_roles == []


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


async def test_create_does_not_raise_when_the_row_already_exists(
    db_session: AsyncSession,
) -> None:
    """A `record.created` webhook for this same org can land first and
    upsert it before this call runs — `create` must tolerate that race
    instead of raising `UniqueViolationError`, and must not clobber the
    webhook's row with this call's narrower field set.
    """
    attio_id = f"test-org-{uuid.uuid4()}"
    repo = OrganizationRepository(db_session)
    await repo.create(attio_id, "Webhook-Written Name", hq_country="AE")

    created = await repo.create(attio_id, "Bot-Written Name", hq_country="US")

    assert created.attio_id == attio_id
    assert created.name == "Webhook-Written Name"
    assert created.hq_country == "AE"


async def test_find_by_place_id_includes_removed_orgs(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    place_id = f"place-{uuid.uuid4()}"
    repo = OrganizationRepository(db_session)
    await repo.update(throwaway_org.attio_id, source_place_id=place_id, is_active=False)

    found = await repo.find_by_place_id(place_id)

    assert found is not None
    assert found.attio_id == throwaway_org.attio_id
    assert await repo.find_by_place_id(f"other-{uuid.uuid4()}") is None


async def test_find_by_domains_matches_exact_overlap_on_active_orgs(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    host = f"{uuid.uuid4().hex}.example"
    repo = OrganizationRepository(db_session)
    await repo.update(throwaway_org.attio_id, domains=[host.title()])  # stored mixed-case

    found = await repo.find_by_domains([host, f"www.{host}"])

    assert found is not None
    assert found.attio_id == throwaway_org.attio_id
    assert await repo.find_by_domains([host.upper()]) is not None  # case-insensitive
    assert await repo.find_by_domains([f"nope-{host}"]) is None
    assert await repo.find_by_domains([]) is None
