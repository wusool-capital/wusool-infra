from sqlalchemy.ext.asyncio import AsyncSession
from wusool_db.models import BuyerRole, Organization

from ddl_commands.modules.buyers.infrastructure.repositories import BuyerRepository


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


async def test_update_applies_fields(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _buyer(db_session, throwaway_org, model="Buy-and-build")

    repo = BuyerRepository(db_session)
    updated = await repo.update(str(role.id), model="Roll-up")

    assert updated is not None
    assert updated.model == "Roll-up"


async def test_get_by_org_attio_id_finds_existing_role(
    db_session: AsyncSession, throwaway_org: Organization
) -> None:
    role = await _buyer(db_session, throwaway_org, model="Buy-and-build")

    repo = BuyerRepository(db_session)
    found = await repo.get_by_org_attio_id(throwaway_org.attio_id)

    assert found is not None
    assert found.id == role.id


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
    upsert it before this call runs — `create` must tolerate that race
    instead of raising `UniqueViolationError`, and must not clobber the
    webhook's row with this call's narrower field set.
    """
    repo = BuyerRepository(db_session)
    await repo.create(throwaway_org.attio_id, model="Webhook-Written Model")

    created = await repo.create(throwaway_org.attio_id, model="Bot-Written Model")

    assert created.org_attio_id == throwaway_org.attio_id
    assert created.model == "Webhook-Written Model"
