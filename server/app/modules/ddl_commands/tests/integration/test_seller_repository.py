from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, SellerRole
from app.modules.ddl_commands.persistence.repositories.sellers_repository import SellerRepository


async def _seller(db_session: AsyncSession, org: Organization, **fields) -> SellerRole:
    role = SellerRole(org_attio_id=org.attio_id, **fields)
    db_session.add(role)
    await db_session.flush()
    return role


async def test_search_by_organization_name_finds_typo_tolerant_match(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.name = "Acme Capital Partners"
    await _seller(db_session, throwaway_org, is_active=True)

    repo = SellerRepository(db_session)
    results = await repo.search_by_organization_name("Acme Captial")  # typo, deliberate
    assert any(r.org_attio_id == throwaway_org.attio_id for r in results)


async def test_search_by_organization_name_excludes_inactive_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.name = "Stale Duplicate Seller Co"
    await _seller(db_session, throwaway_org, is_active=False)

    repo = SellerRepository(db_session)
    results = await repo.search_by_organization_name("Stale Duplicate Seller Co")
    assert not any(r.org_attio_id == throwaway_org.attio_id for r in results)


async def test_update_applies_fields(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _seller(db_session, throwaway_org, outreach_tier="cold")

    repo = SellerRepository(db_session)
    updated = await repo.update(str(role.id), outreach_tier="warm")

    assert updated is not None
    assert updated.outreach_tier == "warm"


async def test_get_by_org_attio_id_finds_existing_active_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _seller(db_session, throwaway_org, outreach_tier="cold", is_active=True)

    repo = SellerRepository(db_session)
    found = await repo.get_by_org_attio_id(throwaway_org.attio_id)

    assert found is not None
    assert found.id == role.id


async def test_get_by_org_attio_id_ignores_inactive_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    await _seller(db_session, throwaway_org, outreach_tier="cold", is_active=False)

    repo = SellerRepository(db_session)
    assert await repo.get_by_org_attio_id(throwaway_org.attio_id) is None


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


async def test_create_does_not_raise_when_the_row_already_exists(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    """A `list-entry.created` webhook for this same role can land first and
    insert it before this call runs — both writes carry the same
    `legacy_entry_id` (Attio's own list-entry id for the just-created
    entry), so `create` must tolerate the conflict on `legacy_entry_id`
    instead of raising `UniqueViolationError`, and must not clobber the
    webhook's row with this call's narrower field set.
    """
    repo = SellerRepository(db_session)
    await repo.create(
        throwaway_org.attio_id,
        legacy_entry_id="entry-1",
        is_active=True,
        outreach_tier="Webhook Tier",
    )

    created = await repo.create(
        throwaway_org.attio_id, legacy_entry_id="entry-1", is_active=True, outreach_tier="Bot Tier"
    )

    assert created.org_attio_id == throwaway_org.attio_id
    assert created.outreach_tier == "Webhook Tier"


async def test_create_allows_a_second_role_for_the_same_org(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    """A second, distinct role for the same org (schema-legal since
    2026-08-28) must insert as its own row rather than raising
    `InvalidColumnReference` — `ON CONFLICT` no longer targets
    `org_attio_id`, which isn't unique anymore.
    """
    repo = SellerRepository(db_session)
    first = await repo.create(throwaway_org.attio_id, legacy_entry_id="entry-a", is_active=True)
    second = await repo.create(throwaway_org.attio_id, legacy_entry_id="entry-b", is_active=True)

    assert first.id != second.id
    assert second.is_active is True
