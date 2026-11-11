"""Matching an outside address to a Person and an Organization."""

from dataclasses import dataclass
from enum import StrEnum

from app.modules.interactions.domain.addresses import domain_of, org_domain_candidates


class Ambiguity(StrEnum):
    SHARED_EMAIL = "shared_email"
    SHARED_DOMAIN = "shared_domain"


@dataclass(frozen=True)
class PersonRef:
    attio_id: str
    organization_id: str | None


@dataclass(frozen=True)
class RecordDirectory:
    """Every live Person and Organization, keyed by lowercase address and domain."""

    people_by_email: dict[str, tuple[PersonRef, ...]]
    org_ids_by_domain: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class LinkResolution:
    person_id: str | None
    organization_id: str | None
    ambiguity: Ambiguity | None


def resolve_link(address: str, directory: RecordDirectory) -> LinkResolution:
    """Links only what is unambiguous. A shared address links nothing; a shared domain
    links no Organization. Both are left for a person to review."""
    people = directory.people_by_email.get(address, ())
    if len(people) > 1:
        return LinkResolution(None, None, Ambiguity.SHARED_EMAIL)
    person = people[0] if people else None
    if person is not None and person.organization_id is not None:
        return LinkResolution(person.attio_id, person.organization_id, None)

    org_id, ambiguity = organization_by_domain(domain_of(address), directory)
    return LinkResolution(person.attio_id if person else None, org_id, ambiguity)


def organization_by_domain(
    domain: str, directory: RecordDirectory
) -> tuple[str | None, Ambiguity | None]:
    for candidate in org_domain_candidates(domain):
        org_ids = directory.org_ids_by_domain.get(candidate, ())
        if len(org_ids) == 1:
            return org_ids[0], None
        if len(org_ids) > 1:
            return None, Ambiguity.SHARED_DOMAIN
    return None, None
