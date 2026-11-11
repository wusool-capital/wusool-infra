"""Read-only list of every live Person's emails, for modules that match mail to CRM records."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person


@dataclass(frozen=True)
class PersonEmails:
    """One live Person with the emails and Organization the mirror holds, as stored."""

    attio_id: str
    emails: tuple[str, ...]
    company_attio_id: str | None


async def list_live_person_emails(session: AsyncSession) -> list[PersonEmails]:
    rows = await session.execute(
        select(Person.attio_id, Person.email, Person.company_attio_id).where(
            Person.removed_at.is_(None)
        )
    )
    return [PersonEmails(attio_id, tuple(emails), company) for attio_id, emails, company in rows]
