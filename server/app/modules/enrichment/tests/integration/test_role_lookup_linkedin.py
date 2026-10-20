"""Real-database coverage for `SqlAlchemyRoleReader.load_linkedin_targets`.
Skips cleanly when no database is reachable (see conftest).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Organization, Person, SellerRole
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.persistence.role_lookup import SqlAlchemyRoleReader


def _person(org: Organization, name: str, *, linkedin: str | None, removed: bool = False) -> Person:
    from datetime import UTC, datetime

    return Person(
        attio_id=f"test-person-{uuid.uuid4()}",
        name=name,
        company_attio_id=org.attio_id,
        linkedin=linkedin,
        job_title="CFO",
        removed_at=datetime.now(UTC) if removed else None,
    )


async def test_seller_contacts_are_capped_and_scrapable_ones_come_first(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    org = Organization(
        attio_id=f"test-org-{uuid.uuid4()}",
        name="Acme Co",
        linkedin="https://www.linkedin.com/company/acme-co",
    )
    db_session.add(org)
    await db_session.flush()
    role = SellerRole(id=uuid.uuid4(), org_attio_id=org.attio_id, is_active=True)
    db_session.add(role)
    db_session.add_all(
        [
            _person(org, "Aaron No-Url", linkedin=None),
            _person(org, "Bea", linkedin="https://www.linkedin.com/in/bea"),
            _person(org, "Cy", linkedin="https://www.linkedin.com/in/cy"),
            _person(org, "Dee", linkedin="https://www.linkedin.com/in/dee"),
            _person(org, "Gone", linkedin="https://www.linkedin.com/in/gone", removed=True),
        ]
    )
    await db_session.flush()

    result = await SqlAlchemyRoleReader(db_sessionmaker).load_linkedin_targets(
        EnrichmentTarget(EnrichmentTargetKind.SELLER, role.id, org.attio_id, org.name)
    )

    assert [c.name for c in result.contacts] == ["Bea", "Cy", "Dee"]
    assert result.company_url == "https://www.linkedin.com/company/acme-co"
    assert all(c.company_name == "Acme Co" for c in result.contacts)


async def test_buyer_contact_is_the_key_contact_only(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Acme Capital")
    db_session.add(org)
    await db_session.flush()
    key = _person(org, "Key Contact", linkedin="https://www.linkedin.com/in/key")
    other = _person(org, "Someone Else", linkedin="https://www.linkedin.com/in/other")
    db_session.add_all([key, other])
    await db_session.flush()
    role = BuyerRole(
        id=uuid.uuid4(),
        org_attio_id=org.attio_id,
        is_active=True,
        key_contact_attio_id=key.attio_id,
    )
    db_session.add(role)
    await db_session.flush()

    result = await SqlAlchemyRoleReader(db_sessionmaker).load_linkedin_targets(
        EnrichmentTarget(EnrichmentTargetKind.BUYER, role.id, org.attio_id, org.name)
    )

    assert [c.name for c in result.contacts] == ["Key Contact"]


async def test_buyer_without_a_key_contact_has_no_contacts(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Acme Capital")
    db_session.add(org)
    await db_session.flush()
    role = BuyerRole(id=uuid.uuid4(), org_attio_id=org.attio_id, is_active=True)
    db_session.add(role)
    await db_session.flush()

    result = await SqlAlchemyRoleReader(db_sessionmaker).load_linkedin_targets(
        EnrichmentTarget(EnrichmentTargetKind.BUYER, role.id, org.attio_id, org.name)
    )

    assert result.contacts == ()


async def test_without_contacts_only_the_company_page_is_returned(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    org = Organization(
        attio_id=f"test-org-{uuid.uuid4()}",
        name="Acme Co",
        linkedin="https://www.linkedin.com/company/acme-co",
    )
    db_session.add(org)
    await db_session.flush()
    role = SellerRole(id=uuid.uuid4(), org_attio_id=org.attio_id, is_active=True)
    db_session.add_all([role, _person(org, "Bea", linkedin="https://www.linkedin.com/in/bea")])
    await db_session.flush()

    result = await SqlAlchemyRoleReader(db_sessionmaker).load_linkedin_targets(
        EnrichmentTarget(EnrichmentTargetKind.SELLER, role.id, org.attio_id, org.name),
        include_contacts=False,
    )

    assert result.contacts == ()
    assert result.company_url == "https://www.linkedin.com/company/acme-co"
