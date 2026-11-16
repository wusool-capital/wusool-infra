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

    changed_orgs = await store.save(AttioObject.ORGANIZATIONS, {org_id: Decimal("12.3456")})
    changed_people = await store.save(AttioObject.PERSON, {person_id: Decimal("3.5")})
    unknown = await store.save(AttioObject.PERSON, {f"{record_prefix}missing": Decimal("1")})

    orgs, people = await store.load(AttioObject.ORGANIZATIONS), await store.load(AttioObject.PERSON)
    assert (changed_orgs, changed_people, unknown) == (1, 1, 0)
    assert orgs[org_id] == Decimal("12.3456")
    assert people[person_id] == Decimal("3.5")
    assert person_id not in orgs
