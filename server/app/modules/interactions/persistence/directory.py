"""Implements `RecordDirectoryPort` through the `organizations` and `ddl_commands` lookups."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ddl_commands import list_live_person_emails
from app.modules.interactions.domain.linking import PersonRef, RecordDirectory
from app.modules.organizations import OrganizationRepository


class SqlAlchemyRecordDirectory:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def load(self) -> RecordDirectory:
        async with self._sessionmaker() as session:
            people = await list_live_person_emails(session)
            orgs = await OrganizationRepository(session).list_live_domains()

        # The mirror doesn't lowercase what Attio holds, so normalise here.
        people_by_email: dict[str, list[PersonRef]] = {}
        for person in people:
            for email in {e.strip().lower() for e in person.emails if e.strip()}:
                people_by_email.setdefault(email, []).append(
                    PersonRef(person.attio_id, person.company_attio_id)
                )

        org_ids_by_domain: dict[str, list[str]] = {}
        for org in orgs:
            for domain in {_bare_domain(d) for d in org.domains if d.strip()}:
                org_ids_by_domain.setdefault(domain, []).append(org.attio_id)

        return RecordDirectory(
            people_by_email={k: tuple(v) for k, v in people_by_email.items()},
            org_ids_by_domain={k: tuple(v) for k, v in org_ids_by_domain.items()},
        )


def _bare_domain(raw: str) -> str:
    """Orgs may store `www.acme.com`; mail comes from `acme.com`."""
    return raw.strip().lower().removeprefix("www.")
