"""Real-database coverage for `SqlAlchemyRoleReader` — confirms it reads
the actual columns enrichment cares about off `seller_roles`/`organizations`,
not just off a fake. Skips cleanly when no DB tunnel is open (see conftest).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, SellerRole
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.enrichment.persistence.role_lookup import SqlAlchemyRoleReader


async def test_current_values_reads_populated_and_missing_fields(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    org = Organization(
        attio_id=f"test-org-{uuid.uuid4()}", name="Acme Co", hq_country="United Arab Emirates"
    )
    db_session.add(org)
    await db_session.flush()

    role = SellerRole(
        id=uuid.uuid4(),
        org_attio_id=org.attio_id,
        est_revenue={"amount": 5_000_000, "currency": "USD"},
        is_active=True,
    )
    db_session.add(role)
    await db_session.flush()

    target = EnrichmentTarget(
        kind=EnrichmentTargetKind.SELLER,
        role_id=role.id,
        org_attio_id=org.attio_id,
        org_name=org.name,
    )
    values = await SqlAlchemyRoleReader(db_sessionmaker).current_values(target)

    assert values["est_revenue"] == {"amount": 5_000_000, "currency": "USD"}
    assert values["hq_country"] == "United Arab Emirates"
    # Never populated on either row — must come back None, not KeyError.
    assert values["location_count"] is None
    assert values["linkedin"] is None


async def test_current_values_for_a_missing_role_returns_none_for_role_fields(
    db_session: AsyncSession, db_sessionmaker
) -> None:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Ghost Org")
    db_session.add(org)
    await db_session.flush()

    target = EnrichmentTarget(
        kind=EnrichmentTargetKind.SELLER,
        role_id=uuid.uuid4(),  # no such role row exists
        org_attio_id=org.attio_id,
        org_name=org.name,
    )
    values = await SqlAlchemyRoleReader(db_sessionmaker).current_values(target)

    assert values["est_revenue"] is None
