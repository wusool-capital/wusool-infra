"""`RoleLookup` against a real database -- the tie-break/`is_active`
filtering matters more than SQLAlchemy can guarantee from unit tests alone
(`created_at`'s `now()` default is transaction-scoped, so rows in one
transaction can share a timestamp). Uses `db_session` (conftest.py), so it
skips cleanly when no database is reachable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models import BuyerRole, Organization, SellerRole
from app.modules.meetings.persistence.role_lookup import RoleLookup


async def _org(session, attio_id: str) -> Organization:
    org = Organization(attio_id=attio_id, name=f"Org {attio_id}")
    session.add(org)
    await session.flush()
    return org


def _buyer_role(
    *,
    org_attio_id: str,
    is_active: bool | None,
    created_at: datetime,
    legacy_entry_id: str | None = None,
) -> BuyerRole:
    return BuyerRole(
        id=uuid4(),
        org_attio_id=org_attio_id,
        is_active=is_active,
        legacy_entry_id=legacy_entry_id,
        created_at=created_at,
    )


def _seller_role(
    *,
    org_attio_id: str,
    is_active: bool | None,
    created_at: datetime,
    legacy_entry_id: str | None = None,
) -> SellerRole:
    return SellerRole(
        id=uuid4(),
        org_attio_id=org_attio_id,
        is_active=is_active,
        legacy_entry_id=legacy_entry_id,
        created_at=created_at,
    )


async def test_newest_active_buyer_role_wins(db_session) -> None:
    org = await _org(db_session, f"org-{uuid4()}")
    older = _buyer_role(
        org_attio_id=org.attio_id,
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        legacy_entry_id="entry-old",
    )
    newer = _buyer_role(
        org_attio_id=org.attio_id,
        is_active=True,
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
        legacy_entry_id="entry-new",
    )
    db_session.add_all([older, newer])
    await db_session.flush()

    result = await RoleLookup(db_session).get_active_buyer_role(org.attio_id)

    assert result is not None
    assert result.id == newer.id
    assert result.legacy_entry_id == "entry-new"


async def test_inactive_and_null_active_rows_are_excluded(db_session) -> None:
    org = await _org(db_session, f"org-{uuid4()}")
    inactive = _buyer_role(org_attio_id=org.attio_id, is_active=False, created_at=datetime.now(UTC))
    null_active = _buyer_role(
        org_attio_id=org.attio_id, is_active=None, created_at=datetime.now(UTC)
    )
    db_session.add_all([inactive, null_active])
    await db_session.flush()

    result = await RoleLookup(db_session).get_active_buyer_role(org.attio_id)

    assert result is None


async def test_no_active_rows_returns_none(db_session) -> None:
    org = await _org(db_session, f"org-{uuid4()}")

    result = await RoleLookup(db_session).get_active_buyer_role(org.attio_id)

    assert result is None


async def test_tie_break_on_identical_created_at_is_deterministic(db_session) -> None:
    org = await _org(db_session, f"org-{uuid4()}")
    same_ts = datetime(2026, 6, 1, tzinfo=UTC)
    a = _buyer_role(org_attio_id=org.attio_id, is_active=True, created_at=same_ts)
    b = _buyer_role(org_attio_id=org.attio_id, is_active=True, created_at=same_ts)
    db_session.add_all([a, b])
    await db_session.flush()
    expected = max(a.id, b.id)

    result = await RoleLookup(db_session).get_active_buyer_role(org.attio_id)

    assert result is not None
    assert result.id == expected


async def test_buyer_lookup_never_returns_a_seller_row(db_session) -> None:
    org = await _org(db_session, f"org-{uuid4()}")
    seller = _seller_role(org_attio_id=org.attio_id, is_active=True, created_at=datetime.now(UTC))
    db_session.add(seller)
    await db_session.flush()

    result = await RoleLookup(db_session).get_active_buyer_role(org.attio_id)

    assert result is None


async def test_newest_active_seller_role_wins(db_session) -> None:
    org = await _org(db_session, f"org-{uuid4()}")
    older = _seller_role(
        org_attio_id=org.attio_id,
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        legacy_entry_id="entry-old",
    )
    newer = _seller_role(
        org_attio_id=org.attio_id,
        is_active=True,
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
        legacy_entry_id="entry-new",
    )
    db_session.add_all([older, newer])
    await db_session.flush()

    result = await RoleLookup(db_session).get_active_seller_role(org.attio_id)

    assert result is not None
    assert result.id == newer.id
    assert result.legacy_entry_id == "entry-new"
