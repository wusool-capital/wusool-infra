"""`SqlAlchemyRecordDirectory` against a real Postgres."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Organization, Person
from app.modules.interactions.domain.linking import PersonRef
from app.modules.interactions.persistence.directory import SqlAlchemyRecordDirectory


async def test_people_and_organizations_are_keyed_by_normalised_address_and_domain(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    org_id, person_id = f"{record_prefix}org", f"{record_prefix}p1"
    stored_email = f"Sara.{record_prefix}@Acme-Test.com "
    domain = f"{record_prefix}acme.example"
    async with sessionmaker() as session, session.begin():
        session.add(Organization(attio_id=org_id, name="Acme", domains=[f"WWW.{domain.upper()}"]))
        await session.flush()
        session.add(
            Person(attio_id=person_id, name="Sara", company_attio_id=org_id, email=[stored_email])
        )

    directory = await SqlAlchemyRecordDirectory(sessionmaker).load()

    assert directory.people_by_email[stored_email.strip().lower()] == (
        PersonRef(person_id, org_id),
    )
    assert directory.org_ids_by_domain[domain.lower()] == (org_id,)


async def test_records_deleted_in_attio_are_left_out(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    gone_org, gone_person = f"{record_prefix}gone-o", f"{record_prefix}gone-p"
    domain = f"{record_prefix}gone.example"
    email = f"gone.{record_prefix}@gone.example"
    removed = datetime(2026, 11, 1, tzinfo=UTC)
    async with sessionmaker() as session, session.begin():
        session.add(
            Organization(attio_id=gone_org, name="Gone", domains=[domain], removed_at=removed)
        )
        session.add(Person(attio_id=gone_person, name="Gone", email=[email], removed_at=removed))

    directory = await SqlAlchemyRecordDirectory(sessionmaker).load()

    assert email not in directory.people_by_email
    assert domain not in directory.org_ids_by_domain


async def test_an_address_held_by_two_people_lists_both(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    email = f"info.{record_prefix}@shared.example"
    async with sessionmaker() as session, session.begin():
        session.add_all(
            [
                Person(attio_id=f"{record_prefix}a", name="A", email=[email]),
                Person(attio_id=f"{record_prefix}b", name="B", email=[email.upper()]),
            ]
        )

    directory = await SqlAlchemyRecordDirectory(sessionmaker).load()

    assert {p.attio_id for p in directory.people_by_email[email]} == {
        f"{record_prefix}a",
        f"{record_prefix}b",
    }


async def test_a_domain_held_by_two_organizations_lists_both(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    domain = f"{record_prefix}twin.example"
    async with sessionmaker() as session, session.begin():
        session.add_all(
            [
                Organization(attio_id=f"{record_prefix}o1", name="One", domains=[domain]),
                Organization(attio_id=f"{record_prefix}o2", name="Two", domains=[domain]),
            ]
        )

    directory = await SqlAlchemyRecordDirectory(sessionmaker).load()

    assert set(directory.org_ids_by_domain[domain]) == {f"{record_prefix}o1", f"{record_prefix}o2"}
