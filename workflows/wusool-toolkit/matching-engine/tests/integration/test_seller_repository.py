import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sellers.infrastructure.models import SellerRole
from app.modules.sellers.infrastructure.repositories import SellerRepository
from app.shared.database.models import Organization


async def test_get_structured_fields_returns_role_row(
    db_session: AsyncSession, any_seller_role: SellerRole
) -> None:
    repo = SellerRepository(db_session)
    fields = await repo.get_structured_fields(str(any_seller_role.id))
    assert fields is not None
    assert fields.id == any_seller_role.id


async def test_get_eligible_sellers_excludes_removed_rows(db_session: AsyncSession) -> None:
    """A seller removed via `/remove-seller` (ddl-commands, `removed_at` set)
    must never be suggestible as a `/find-match` candidate.
    """
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Removed Seller Test Org")
    db_session.add(org)
    await db_session.flush()

    removed = SellerRole(org_attio_id=org.attio_id, removed_at=datetime.now(UTC))
    db_session.add(removed)
    await db_session.flush()

    repo = SellerRepository(db_session)
    candidates = await repo.get_eligible_sellers(limit=1000)
    assert removed.id not in {c.id for c in candidates}
