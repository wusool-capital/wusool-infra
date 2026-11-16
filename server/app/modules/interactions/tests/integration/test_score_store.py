"""The score store on a real Postgres, for both objects."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Organization, Person
from app.modules.interactions.domain.attio_fields import AttioObject
from app.modules.interactions.persistence.score_store import SqlAlchemyScoreStore


async def test_scores_load_and_save_for_organizations_and_people(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    org_id, person_id = f"{record_prefix}o", f"{record_prefix}p"
    async with sessionmaker() as session, session.begin():
        session.add(Organization(attio_id=org_id, name="Acme"))
        await session.flush()
        session.add(Person(attio_id=person_id, name="Sara", company_attio_id=org_id))
    store = SqlAlchemyScoreStore(sessionmaker)

    await store.save(AttioObject.ORGANIZATIONS, {org_id: Decimal("12.3456")})
    await store.save(AttioObject.PERSON, {person_id: Decimal("3.5")})
    # A record the mirror does not hold changes nothing and does not fail.
    await store.save(AttioObject.PERSON, {f"{record_prefix}missing": Decimal("1")})

    orgs, people = await store.load(AttioObject.ORGANIZATIONS), await store.load(AttioObject.PERSON)
    assert orgs[org_id] == Decimal("12.3456")
    assert people[person_id] == Decimal("3.5")
    assert person_id not in orgs


async def test_several_scores_saved_at_once_all_land(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    ids = [f"{record_prefix}o{i}" for i in range(3)]
    async with sessionmaker() as session, session.begin():
        session.add_all([Organization(attio_id=i, name=f"Org {i}") for i in ids])
    store = SqlAlchemyScoreStore(sessionmaker)

    await store.save(AttioObject.ORGANIZATIONS, {i: Decimal(n + 1) for n, i in enumerate(ids)})

    stored = await store.load(AttioObject.ORGANIZATIONS)
    assert [stored[i] for i in ids] == [Decimal(1), Decimal(2), Decimal(3)]
