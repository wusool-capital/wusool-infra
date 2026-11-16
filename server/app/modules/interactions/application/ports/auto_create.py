"""What auto-create reads and writes: unknown outside addresses, and new Attio records."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


@dataclass(frozen=True)
class Candidate:
    """An outside address with no Person yet, and the evidence it is worth creating."""

    email: str
    domain: str
    # As the mail or calendar showed it; None when no row has one.
    name: str | None
    two_way_thread: bool
    attended_meeting: bool


class CandidateSourcePort(Protocol):
    async def candidates(self, internal_domains: tuple[str, ...]) -> tuple[Candidate, ...]:
        """Unlinked outside addresses with a two-way thread or an attended meeting."""
        ...


class RecordCreatorPort(Protocol):
    async def person_exists(self, email: str) -> bool:
        """Asks Attio itself, because the Postgres copy lags the webhook."""
        ...

    async def create_organization(self, name: str, domain: str) -> str:
        """Returns the new Organization's Attio id."""
        ...

    async def create_person(self, name: str, email: str, organization_id: str | None) -> str:
        """Returns the new Person's Attio id."""
        ...


class CreatedKind(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"


class CreatedKeysPort(Protocol):
    """Our own record of what we created, so a retry or a restart never creates it twice."""

    async def get(self, kind: CreatedKind, key: str) -> str | None:
        """The Attio id created for this email (a Person) or domain (an Organization)."""
        ...

    async def save(self, kind: CreatedKind, key: str, record_id: str) -> None: ...
