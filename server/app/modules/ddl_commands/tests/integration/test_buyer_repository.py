from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Organization
from app.modules.ddl_commands.persistence.repositories.buyers_repository import BuyerRepository


async def _buyer(db_session: AsyncSession, org: Organization, **fields) -> BuyerRole:
    role = BuyerRole(org_attio_id=org.attio_id, **fields)
    db_session.add(role)
    await db_session.flush()
    return role


async def test_search_by_organization_name_finds_typo_tolerant_match(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.name = "Blue Horizon Buyers"
    await _buyer(db_session, throwaway_org, is_active=True)

    repo = BuyerRepository(db_session)
    results = await repo.search_by_organization_name("Blue Horizen Buyers")  # typo, deliberate
    assert any(r.org_attio_id == throwaway_org.attio_id for r in results)


async def test_search_by_organization_name_excludes_inactive_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    throwaway_org.name = "Stale Duplicate Buyer Co"
    await _buyer(db_session, throwaway_org, is_active=False)

    repo = BuyerRepository(db_session)
    results = await repo.search_by_organization_name("Stale Duplicate Buyer Co")
    assert not any(r.org_attio_id == throwaway_org.attio_id for r in results)


async def test_update_applies_fields(db_session: AsyncSession, throwaway_org: Organization) -> None:
    role = await _buyer(db_session, throwaway_org, model="Buy-and-build")

    repo = BuyerRepository(db_session)
    updated = await repo.update(str(role.id), model="Roll-up")

    assert updated is not None
    assert updated.model == "Roll-up"


async def test_get_by_org_attio_id_finds_existing_active_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _buyer(db_session, throwaway_org, model="Buy-and-build", is_active=True)

    repo = BuyerRepository(db_session)
    found = await repo.get_by_org_attio_id(throwaway_org.attio_id)

    assert found is not None
    assert found.id == role.id


async def test_get_by_org_attio_id_ignores_inactive_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    await _buyer(db_session, throwaway_org, model="Buy-and-build", is_active=False)

    repo = BuyerRepository(db_session)
    assert await repo.get_by_org_attio_id(throwaway_org.attio_id) is None


async def test_get_by_org_attio_id_returns_none_when_no_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    repo = BuyerRepository(db_session)
    found = await repo.get_by_org_attio_id(throwaway_org.attio_id)
    assert found is None


async def test_create_inserts_a_new_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    repo = BuyerRepository(db_session)
    created = await repo.create(throwaway_org.attio_id, model="Model 1 (Network)")

    assert created.org_attio_id == throwaway_org.attio_id
    assert created.model == "Model 1 (Network)"


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
    repo = BuyerRepository(db_session)
    await repo.create(
        throwaway_org.attio_id,
        legacy_entry_id="entry-1",
        is_active=True,
        model="Webhook-Written Model",
    )

    created = await repo.create(
        throwaway_org.attio_id, legacy_entry_id="entry-1", is_active=True, model="Bot-Written Model"
    )

    assert created.org_attio_id == throwaway_org.attio_id
    assert created.model == "Webhook-Written Model"


async def test_create_allows_a_second_role_for_the_same_org(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    """A second, distinct role for the same org (schema-legal since
    2026-08-28) must insert as its own row rather than raising
    `InvalidColumnReference` — `ON CONFLICT` no longer targets
    `org_attio_id`, which isn't unique anymore.
    """
    repo = BuyerRepository(db_session)
    first = await repo.create(throwaway_org.attio_id, legacy_entry_id="entry-a", is_active=True)
    second = await repo.create(throwaway_org.attio_id, legacy_entry_id="entry-b", is_active=True)

    assert first.id != second.id
    assert second.is_active is True
