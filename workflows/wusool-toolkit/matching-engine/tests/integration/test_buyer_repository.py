import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.buyers.infrastructure.models import BuyerRole
from app.modules.buyers.infrastructure.repositories import BuyerRepository
from app.shared.database.models import Organization


async def test_get_requirement_profile_returns_role_row(
    db_session: AsyncSession, any_buyer_role: BuyerRole
) -> None:
    repo = BuyerRepository(db_session)
    profile = await repo.get_requirement_profile(str(any_buyer_role.id))
    assert profile is not None
    assert profile.id == any_buyer_role.id


async def test_search_by_organization_name_excludes_removed_rows(db_session: AsyncSession) -> None:
    """A buyer removed via `/remove-buyer` (ddl-commands, `removed_at` set)
    must not be offered as a `/find-match` target.
    """
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Removed Buyer Zephyr Corp")
    db_session.add(org)
    await db_session.flush()

    removed = BuyerRole(org_attio_id=org.attio_id, removed_at=datetime.now(UTC))
    db_session.add(removed)
    await db_session.flush()

    repo = BuyerRepository(db_session)
    results = await repo.search_by_organization_name("Zephyr")
    assert removed.id not in {r.id for r in results}
