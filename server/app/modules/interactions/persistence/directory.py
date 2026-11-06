"""Implements `RecordDirectoryPort` from the mirrored `person` and `organizations` tables."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Organization, Person
from app.modules.interactions.domain.linking import PersonRef, RecordDirectory


class SqlAlchemyRecordDirectory:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def load(self) -> RecordDirectory:
        people_stmt = select(Person.attio_id, Person.email, Person.company_attio_id).where(
            Person.removed_at.is_(None)
        )
        orgs_stmt = select(Organization.attio_id, Organization.domains).where(
            Organization.removed_at.is_(None)
        )
        async with self._sessionmaker() as session:
            people = (await session.execute(people_stmt)).all()
            orgs = (await session.execute(orgs_stmt)).all()

        # The mirror doesn't lowercase what Attio holds, so normalise here.
        people_by_email: dict[str, list[PersonRef]] = {}
        for attio_id, emails, company_id in people:
            for email in {e.strip().lower() for e in emails if e.strip()}:
                people_by_email.setdefault(email, []).append(PersonRef(attio_id, company_id))

        org_ids_by_domain: dict[str, list[str]] = {}
        for attio_id, domains in orgs:
            for domain in {_bare_domain(d) for d in domains if d.strip()}:
                org_ids_by_domain.setdefault(domain, []).append(attio_id)

        return RecordDirectory(
            people_by_email={k: tuple(v) for k, v in people_by_email.items()},
            org_ids_by_domain={k: tuple(v) for k, v in org_ids_by_domain.items()},
        )


def _bare_domain(raw: str) -> str:
    """Orgs may store `www.acme.com`; mail comes from `acme.com`."""
    return raw.strip().lower().removeprefix("www.")
